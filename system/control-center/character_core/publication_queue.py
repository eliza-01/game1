"""Sequential component publication jobs. Component store owns Roblox IDs.

No credentials are persisted. Restart interrupts the queue; explicit retry uses
the component store's saved Open Cloud operation rather than uploading twice.
"""
import copy
import json
import logging
from pathlib import Path
from threading import Lock, Thread
import time
from uuid import UUID
from character_core.components import ComponentConflict

ACTIVE={'queued','running'}


class CharacterPublicationQueue:
    def __init__(self,root,components,*,on_published=lambda:None):
        self.components=components;self.on_published=on_published
        self.path=Path(root)/'.control-center/character-publication-queue.json'
        self.lock=Lock();self.jobs=[]
        try:
            if self.path.is_file():
                saved=json.loads(self.path.read_text(encoding='utf8'))
                if saved.get('schema_version')!=1 or not isinstance(saved.get('jobs'),list):raise ValueError('unsupported queue file')
                self.jobs=saved['jobs'][-20:]
                for job in self.jobs:
                    if job['status'] in ACTIVE:
                        job['status']='interrupted';job['finished_at']=time.time()
                        for item in job['items']:
                            if item['status'] in {'queued','publishing'}:
                                item.update(status='interrupted',step='Host Agent restarted; retry explicitly')
                self._save()
        except (OSError,ValueError,KeyError,TypeError):
            self.jobs=[]
            logging.warning('Character publication queue could not be restored; component publication IDs remain in SQLite')

    def _save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(dict(schema_version=1,jobs=self.jobs),indent=2),encoding='utf8')
        temporary.replace(self.path)

    def get(self,job_id=None):
        with self.lock:
            job=next((j for j in self.jobs if j['id']==job_id),None) if job_id else (self.jobs[-1] if self.jobs else None)
            return copy.deepcopy(job)

    def start(self,items,request_id,credentials):
        try:request_id=str(UUID(str(request_id)))
        except (ValueError,TypeError,AttributeError):raise ValueError('request_id must be a UUID')
        if not isinstance(items,list) or not 1<=len(items)<=100:raise ValueError('select 1–100 components')
        normalized=[]
        for item in items:
            if not isinstance(item,dict) or item.get('kind') not in {'rig','part'}:raise ValueError('invalid queue item')
            key=item.get('id');revision=item.get('revision')
            if not isinstance(key,str) or not isinstance(revision,int) or isinstance(revision,bool):raise ValueError('invalid queue identity/revision')
            normalized.append(dict(kind=item['kind'],id=key,revision=revision))
        if len({(i['kind'],i['id']) for i in normalized})!=len(normalized):raise ValueError('duplicate queue item')
        # Rig first; within each group preserve the user's selection order.
        normalized.sort(key=lambda i:i['kind']!='rig')
        with self.lock:
            existing=next((j for j in self.jobs if j['id']==request_id),None)
            if existing:
                previous=[{k:i[k] for k in ('kind','id','revision')} for i in existing['items']]
                if previous!=normalized:raise ComponentConflict('request_id is already used for a different selection')
                return copy.deepcopy(existing)
            if any(j['status'] in ACTIVE for j in self.jobs):raise ComponentConflict('another character publication queue is running')
            for item in normalized:
                row=self.components.get(item['kind'],item['id'])
                if not row:raise ValueError('unknown component: '+item['id'])
                if row['revision']!=item['revision']:raise ComponentConflict(item['id']+' changed; refresh the component list')
            job=dict(schema_version=1,id=request_id,status='queued',started_at=time.time(),finished_at=None,
                items=[dict(**i,status='queued',step='Waiting',error='',warning='',asset_id='') for i in normalized])
            self.jobs=(self.jobs+[job])[-20:];self._save();snapshot=copy.deepcopy(job)
        Thread(target=self._run,args=(job,credentials),name='character-publication-queue',daemon=True).start()
        return snapshot

    def _update(self,job,item=None,**changes):
        with self.lock:
            (item if item is not None else job).update(changes);self._save()

    def _run(self,job,credentials):
        try:self._work(job,credentials)
        except Exception as error:
            logging.exception('Character publication queue worker failed')
            try:
                for item in job['items']:
                    if item['status'] in {'queued','publishing'}:
                        self._update(job,item,status='failed',step='Queue worker failed',error=str(error))
                self._update(job,status='completed_with_errors',finished_at=time.time())
            except OSError:logging.exception('Could not save interrupted character publication queue')

    def _work(self,job,credentials):
        self._update(job,status='running')
        for item in job['items']:
            self._update(job,item,status='publishing',step='Preparing publication')
            try:
                row=self.components.get(item['kind'],item['id'])
                if not row or row['revision']!=item['revision']:raise ComponentConflict('component changed after queue creation')
                if row['published_revision']==row['revision'] and row['model_asset_id']:
                    self._update(job,item,status='skipped',step='Already published',asset_id=row['model_asset_id'])
                    continue
                result=self.components.publish(item['kind'],item['id'],credentials,
                    expected_revision=item['revision'],
                    on_progress=lambda step:self._update(job,item,step=step))
                warning=''
                try:self.on_published()
                except Exception as error:warning='Published; character registry refresh failed: '+str(error)
                self._update(job,item,status='succeeded',step='Published',asset_id=result['model_asset_id'],warning=warning)
            except Exception as error:
                # A local export error may happen after the ID was committed.
                # Preserve success and report its refresh warning, never reupload.
                current=self.components.get(item['kind'],item['id'])
                if current and current['published_revision']==item['revision'] and current['model_asset_id']:
                    self._update(job,item,status='succeeded',step='Published; refresh needs attention',
                        asset_id=current['model_asset_id'],warning=str(error))
                else:self._update(job,item,status='failed',step='Failed',error=str(error))
        issues=any(i['status']=='failed' or i['warning'] for i in job['items'])
        self._update(job,status='completed_with_errors' if issues else 'completed',finished_at=time.time())
