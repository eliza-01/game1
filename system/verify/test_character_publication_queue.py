"""Queue sequencing/progress/recovery. No external uploads or live registry writes."""
import json
from pathlib import Path
import sys
import tempfile
from threading import Event
import time
from uuid import uuid4
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'control-center'))
from character_core.publication_queue import CharacterPublicationQueue
from character_core.components import ComponentConflict


class Components:
    def __init__(self):
        self.rows={};self.calls=[];self.entered=Event();self.release=Event();self.release.set();self.fail=set()
        for kind,key in [('rig','human'),('part','newborn_upper'),('part','eyes_01')]:
            self.rows[kind,key]=dict(kind=kind,id=key,revision=1,published_revision=0,model_asset_id='')
    def get(self,kind,key):return self.rows.get((kind,key))
    def publish(self,kind,key,credentials,*,expected_revision=None,on_progress=None):
        row=self.rows[kind,key]
        if row['revision']!=expected_revision:raise ComponentConflict('changed')
        self.calls.append(key);on_progress('Uploading FBX to Roblox');self.entered.set()
        if not self.release.wait(4):raise TimeoutError('fixture was not released')
        if key in self.fail:raise RuntimeError('fixture upload failed')
        row.update(published_revision=row['revision'],model_asset_id='123');return row


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.store=Components();self.queue=CharacterPublicationQueue(self.root,self.store)
        self.credentials={'apiKey':'DO_NOT_PERSIST','creatorId':'1'}
    def items(self):return [dict(kind='part',id='eyes_01',revision=1),dict(kind='rig',id='human',revision=1),dict(kind='part',id='newborn_upper',revision=1)]
    def wait_done(self,queue,job_id):
        deadline=time.monotonic()+4
        while time.monotonic()<deadline:
            job=queue.get(job_id)
            if job['status'] not in {'queued','running'}:return job
            time.sleep(.01)
        self.fail('publication worker did not finish')

    def test_sequential_rig_first_live_progress_and_private_credentials(self):
        self.store.release.clear();job=self.queue.start(self.items(),str(uuid4()),self.credentials)
        self.assertTrue(self.store.entered.wait(2))
        progress=self.queue.get(job['id']);self.assertEqual(progress['items'][0]['id'],'human')
        self.assertEqual(progress['items'][0]['step'],'Uploading FBX to Roblox')
        self.assertEqual(progress['items'][1]['status'],'queued')
        self.assertNotIn('DO_NOT_PERSIST',self.queue.path.read_text())
        self.assertNotIn('apiKey',json.dumps(progress))
        self.store.release.set();done=self.wait_done(self.queue,job['id'])
        self.assertEqual(done['status'],'completed');self.assertEqual(self.store.calls,['human','eyes_01','newborn_upper'])
        self.assertTrue(all(i['asset_id']=='123' for i in done['items']))

    def test_failed_item_does_not_stop_remaining_items(self):
        self.store.fail.add('eyes_01');job=self.queue.start(self.items(),str(uuid4()),self.credentials)
        done=self.wait_done(self.queue,job['id'])
        self.assertEqual(done['status'],'completed_with_errors')
        self.assertEqual([i['status'] for i in done['items']],['succeeded','failed','succeeded'])

    def test_idempotent_request_and_conflicting_queue(self):
        self.store.release.clear();ident=str(uuid4());a=self.queue.start(self.items(),ident,self.credentials)
        self.assertTrue(self.store.entered.wait(2))
        b=self.queue.start(self.items(),ident,self.credentials);self.assertEqual(a['id'],b['id'])
        with self.assertRaises(ComponentConflict):self.queue.start(self.items(),str(uuid4()),self.credentials)
        with self.assertRaises(ComponentConflict):self.queue.start(self.items()[:1],ident,self.credentials)
        self.store.release.set();self.wait_done(self.queue,ident);self.assertEqual(len(self.store.calls),3)

    def test_already_current_skips_without_upload(self):
        self.store.rows['part','eyes_01'].update(published_revision=1,model_asset_id='999')
        job=self.queue.start([self.items()[0]],str(uuid4()),self.credentials)
        done=self.wait_done(self.queue,job['id']);self.assertEqual(done['items'][0]['status'],'skipped')
        self.assertEqual(self.store.calls,[])

    def test_changed_revision_rejected_before_any_upload(self):
        self.store.rows['part','eyes_01']['revision']=2
        with self.assertRaises(ComponentConflict):self.queue.start(self.items(),str(uuid4()),self.credentials)
        self.assertEqual(self.store.calls,[]);self.assertIsNone(self.queue.get())

    def test_restart_marks_incomplete_jobs_interrupted_without_automatic_upload(self):
        self.queue.path.parent.mkdir(parents=True,exist_ok=True)
        self.queue.path.write_text(json.dumps({'schema_version':1,'jobs':[dict(id=str(uuid4()),status='running',
            items=[dict(kind='part',id='eyes_01',revision=1,status='publishing')])]}))
        restarted=CharacterPublicationQueue(self.root,self.store);job=restarted.get()
        self.assertEqual(job['status'],'interrupted');self.assertEqual(job['items'][0]['status'],'interrupted')
        self.assertEqual(self.store.calls,[])

    def test_successful_publication_with_registry_failure_is_not_reuploaded(self):
        def bad_export():raise OSError('registry unavailable')
        queue=CharacterPublicationQueue(self.root,self.store,on_published=bad_export)
        job=queue.start([self.items()[0]],str(uuid4()),self.credentials);done=self.wait_done(queue,job['id'])
        self.assertEqual(done['items'][0]['status'],'succeeded');self.assertIn('registry',done['items'][0]['warning'])
        self.assertEqual(len(self.store.calls),1)


if __name__=='__main__':unittest.main()
