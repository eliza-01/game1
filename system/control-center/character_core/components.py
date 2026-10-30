"""Modular Characters registry v1. Existing archetypes/animation tables are untouched.

Inspection is non-registering; commit uses an immutable FBX snapshot, optimistic
revisions and explicit replacement approval. External uploads are checkpoints.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import shutil
import threading
import time
import uuid
from sqlite_connection import connect
from services.texture_atlas_registry import AtlasRegistry
from character_core.part_names import parse_part, rig_id, skeleton_matches, TOKEN
from character_core.component_fbx import inspect_fbx

_LOCK=threading.RLock()


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for data in iter(lambda:f.read(1024*1024),b''):h.update(data)
    return h.hexdigest()


class ComponentConflict(ValueError):
    pass


class CharacterComponents:
    def __init__(self,root,*,analyzer=inspect_fbx):
        self.root=Path(root).resolve();self.db=self.root/'.control-center/game1.db'
        self.db.parent.mkdir(parents=True,exist_ok=True);self.analyze=analyzer
        # Online backup before the first additive migration; safe with WAL.
        with connect(self.db) as db:
            exists=db.execute("SELECT 1 FROM sqlite_master WHERE name='character_component_schema'").fetchone()
            if not exists:
                backup=self.db.parent/'backups'/('before_character_components_'+uuid.uuid4().hex+'.db')
                backup.parent.mkdir(exist_ok=True)
                with connect(backup) as target:db.backup(target)
            db.executescript('''
                CREATE TABLE IF NOT EXISTS character_component_schema(version INTEGER PRIMARY KEY);
                INSERT OR IGNORE INTO character_component_schema VALUES(1);
                CREATE TABLE IF NOT EXISTS character_component_records(
                    kind TEXT NOT NULL,id TEXT NOT NULL,rig_id TEXT NOT NULL,slot TEXT NOT NULL,
                    set_id TEXT NOT NULL DEFAULT '',gender TEXT NOT NULL DEFAULT 'common',role TEXT NOT NULL,
                    revision INTEGER NOT NULL,content_sha256 TEXT NOT NULL,source_path TEXT NOT NULL,
                    prepared_path TEXT NOT NULL,prepared_sha256 TEXT NOT NULL,metadata_json TEXT NOT NULL,
                    model_asset_id TEXT NOT NULL DEFAULT '',published_revision INTEGER NOT NULL DEFAULT 0,
                    pending_operation TEXT NOT NULL DEFAULT '',created_at REAL NOT NULL,
                    PRIMARY KEY(kind,id));
                CREATE TABLE IF NOT EXISTS character_component_sets(id TEXT PRIMARY KEY,created_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS character_component_imports(
                    id TEXT PRIMARY KEY,plan_json TEXT NOT NULL,committed INTEGER NOT NULL DEFAULT 0,created_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS character_component_history(
                    id INTEGER PRIMARY KEY,kind TEXT NOT NULL,component_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,record_json TEXT NOT NULL,changed_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS character_component_publications(
                    id INTEGER PRIMARY KEY,kind TEXT NOT NULL,component_id TEXT NOT NULL,revision INTEGER NOT NULL,
                    asset_id TEXT NOT NULL,operation_path TEXT NOT NULL,published_at REAL NOT NULL);
            ''')
        self.atlases=AtlasRegistry(self.root)

    def get(self,kind,key):
        if kind not in {'rig','part'}:raise ValueError('invalid component kind')
        with connect(self.db) as db:
            row=db.execute('SELECT * FROM character_component_records WHERE kind=? AND id=?',(kind,key)).fetchone()
        return dict(row) if row else None

    def _snapshot_row(self,row):
        row=dict(row);row['metadata']=json.loads(row.pop('metadata_json'))
        row['status']='published' if row['published_revision']==row['revision'] else ('replacement_pending' if row['model_asset_id'] else 'registered')
        row['atlas']=self.atlases.binding('character_part',row['id']) if row['kind']=='part' else None
        return row

    def publication_metadata(self,row):
        """A staged revision must not change the bind recipe of the live asset."""
        if not row['model_asset_id'] or row['published_revision']==row['revision']:
            return json.loads(row['metadata_json'])
        with connect(self.db) as db:
            old=db.execute('''SELECT record_json FROM character_component_history
                WHERE kind=? AND component_id=? AND revision=? ORDER BY id DESC LIMIT 1''',
                (row['kind'],row['id'],row['published_revision'])).fetchone()
        if not old:raise ValueError('published metadata unavailable for '+row['id'])
        record=json.loads(old['record_json'])
        if record['model_asset_id']!=row['model_asset_id']:raise ValueError('published metadata asset mismatch')
        return json.loads(record['metadata_json'])

    def snapshot(self):
        with connect(self.db) as db:
            rows=db.execute("SELECT * FROM character_component_records ORDER BY CASE kind WHEN 'rig' THEN 0 ELSE 1 END,id").fetchall()
            sets=[r['id'] for r in db.execute('SELECT id FROM character_component_sets ORDER BY id')]
        return dict(schema_version=1,items=[self._snapshot_row(r) for r in rows],sets=sets,
                    atlas_families=self.atlases.catalog(domain='character'))

    def inspect(self,source):
        # Freeze the bytes selected by the native picker. A later user edit cannot
        # silently change what is committed after the confirmation dialog.
        ident=uuid.uuid4().hex
        directory=self.root/'.control-center/character-component-staging'/ident
        directory.mkdir(parents=True);frozen=directory/'source.fbx'
        shutil.copy2(Path(source).resolve(),frozen)
        try:
            info=self.analyze(self.root,frozen)
            key=rig_id(info['armature'])
            if not info['parts']:raise ValueError('FBX has no parts')
            for bones in [info['bones'],*(p['skeleton'] for p in info['parts'])]:
                for bone in bones:
                    if not TOKEN.fullmatch(bone['name']) or len(bone['matrix'])!=16 or not all(math.isfinite(v) for v in bone['matrix']):
                        raise ValueError('bone names must be lower_case_snake_case with finite bind matrices')
            parts=[]
            for part in info['parts']:
                meta=parse_part(part['name'])
                parts.append({**part,**meta,'rig_id':key})
            if len({p['id'] for p in parts})!=len(parts):raise ValueError('duplicate mesh names')
            old=self.get('rig',key)
            if old:skeleton_matches(json.loads(old['metadata_json'])['bones'],info['bones'])
            rows=[]
            for p in parts:
                old_part=self.get('part',p['id'])
                if old_part and old_part['rig_id']!=key:raise ValueError(p['id']+': belongs to another rig')
                rows.append(dict(id=p['id'],slot=p['slot'],set_id=p['set_id'],role=p['role'],
                    vertices=p['vertices'],triangles=p['triangles'],
                    existing_revision=old_part['revision'] if old_part else 0,
                    published_asset_id=old_part['model_asset_id'] if old_part else '',
                    content_unchanged=bool(old_part and old_part['content_sha256']==p['content_sha256'])))
            plan=dict(schema_version=1,token=ident,source=str(frozen.relative_to(self.root)),sha256=sha(frozen),
                rig_id=key,bones=info['bones'],armature=info['armature'],parts=parts,rows=rows,
                rig_revision=old['revision'] if old else 0)
            with connect(self.db) as db:
                db.execute('INSERT INTO character_component_imports(id,plan_json,created_at) VALUES(?,?,?)',
                           (ident,json.dumps(plan),time.time()))
            return dict(schema_version=1,token=ident,rig_id=key,bone_count=len(info['bones']),parts=rows,
                new_sets=sorted({p['set_id'] for p in parts if p['set_id']} - set(self.snapshot()['sets'])),
                conflicts=[p for p in rows if p['published_asset_id']])
        except Exception:
            shutil.rmtree(directory)
            raise

    def register(self,token,replacements):
        with _LOCK:
            with connect(self.db) as db:
                saved=db.execute('SELECT * FROM character_component_imports WHERE id=?',(token,)).fetchone()
            if not saved:raise ValueError('unknown inspection; choose FBX again')
            if saved['committed']:return self.snapshot()
            plan=json.loads(saved['plan_json']);frozen=self.root/plan['source']
            if not frozen.is_file() or sha(frozen)!=plan['sha256']:raise ComponentConflict('inspection source changed; choose FBX again')
            required={p['id'] for p in plan['rows'] if p['published_asset_id']}
            if not isinstance(replacements,list) or set(replacements)!=required:
                raise ComponentConflict('explicit approval required for every published part in this FBX')
            def validate(db):
                for kind,key,revision in [('rig',plan['rig_id'],plan['rig_revision']),
                    *(('part',p['id'],p['existing_revision']) for p in plan['rows'])]:
                    row=db.execute('SELECT revision,pending_operation,model_asset_id FROM character_component_records WHERE kind=? AND id=?',(kind,key)).fetchone()
                    if (row['revision'] if row else 0)!=revision or (row and row['pending_operation']):
                        raise ComponentConflict('catalog changed or publication pending; inspect FBX again')
                    if kind=='part':
                        inspected=next(p for p in plan['rows'] if p['id']==key)
                        if (row['model_asset_id'] if row else '')!=inspected['published_asset_id']:
                            raise ComponentConflict('part was published after inspection; inspect FBX again')
            with connect(self.db) as db:validate(db)
            folder=self.root/'assets/source/character_components/imports'/token
            # game1 is source-only: startup migrates/removes assets/prepared.
            # Extracted component FBX files are canonical publication inputs.
            prepared=self.root/'assets/source/character_components'/token
            folder.mkdir(parents=True,exist_ok=True);shutil.copy2(frozen,folder/'source.fbx')
            info=self.analyze(self.root,folder/'source.fbx',prepared)
            skeleton_matches(plan['bones'],info['bones'])
            if {p['name']:p['content_sha256'] for p in info['parts']}!={p['name']:p['content_sha256'] for p in plan['parts']}:
                raise ComponentConflict('FBX changed during extraction')
            entries=[('rig',plan['rig_id'],dict(bones=plan['bones'],armature=plan['armature']),None)]
            entries.extend(('part',p['id'],p,p) for p in plan['parts'])
            with connect(self.db) as db:
                db.execute('BEGIN IMMEDIATE');validate(db)
                for kind,key,meta,part in entries:
                    old=db.execute('SELECT * FROM character_component_records WHERE kind=? AND id=?',(kind,key)).fetchone()
                    if old and kind=='rig':continue # compatible rig is reused, not republished
                    content=part['content_sha256'] if part else hashlib.sha256(json.dumps(plan['bones'],sort_keys=True).encode()).hexdigest()
                    if old and old['content_sha256']==content and key not in required:continue
                    artifact=prepared/((key if part else 'rig')+'.fbx')
                    if not artifact.is_file() or artifact.stat().st_size==0:raise ValueError('missing extracted FBX: '+key)
                    if old:db.execute('INSERT INTO character_component_history(kind,component_id,revision,record_json,changed_at) VALUES(?,?,?,?,?)',
                        (kind,key,old['revision'],json.dumps(dict(old)),time.time()))
                    revision=old['revision']+1 if old else 1
                    db.execute('''INSERT INTO character_component_records
                        (kind,id,rig_id,slot,set_id,gender,role,revision,content_sha256,source_path,prepared_path,prepared_sha256,metadata_json,created_at)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(kind,id) DO UPDATE SET
                        revision=excluded.revision,content_sha256=excluded.content_sha256,source_path=excluded.source_path,
                        prepared_path=excluded.prepared_path,prepared_sha256=excluded.prepared_sha256,metadata_json=excluded.metadata_json''',
                        (kind,key,plan['rig_id'],part['slot'] if part else 'rig',part['set_id'] if part else '',
                         part['gender'] if part else 'common',part['role'] if part else 'core',revision,content,
                         str((folder/'source.fbx').relative_to(self.root)),str(artifact.relative_to(self.root)),sha(artifact),json.dumps(meta),time.time()))
                    if part and part['set_id']:
                        db.execute('INSERT OR IGNORE INTO character_component_sets VALUES(?,?)',(part['set_id'],time.time()))
                db.execute('UPDATE character_component_imports SET committed=1 WHERE id=?',(token,))
            self.export()
            return self.snapshot()

    def bind_atlas(self,key,variant,revision):
        if not self.get('part',key):raise ValueError('unknown part')
        # Preserve explicitly bound legacy shared variants. New choices are
        # domain-scoped in the Character catalog and Character authoring route.
        self.atlases.bind('character_part',key,int(variant),expected_revision=revision)
        self.export();return self.snapshot()

    def publish(self,kind,key,credentials,*,expected_revision=None,on_progress=None):
        from opencloud_assets import create_model_asset,wait_for_operation
        progress=on_progress or (lambda step:None)
        progress('Waiting for publication lock')
        with _LOCK:
            row=self.get(kind,key)
            if not row:raise ValueError('unknown component')
            if expected_revision is not None and row['revision']!=expected_revision:
                raise ComponentConflict('component revision changed; refresh and retry')
            if row['published_revision']==row['revision']:return self._snapshot_row(row)
            progress('Checking prepared FBX')
            path=self.root/row['prepared_path']
            if not path.is_file() or sha(path)!=row['prepared_sha256']:raise ValueError('prepared FBX changed; register again')
            operation=row['pending_operation']
            if not operation:
                progress('Uploading FBX to Roblox')
                operation=create_model_asset(path,display_name=key,description=credentials.get('description') or 'game1 character component',
                    creator_type=credentials['creatorType'],creator_id=credentials['creatorId'],api_key=credentials['apiKey'])
                with connect(self.db) as db:db.execute('UPDATE character_component_records SET pending_operation=? WHERE kind=? AND id=?',(operation,kind,key))
            # A failed wait retains the operation: retry polls it, never reuploads.
            progress('Roblox is processing the model' if not row['pending_operation'] else 'Resuming saved Roblox operation')
            result=wait_for_operation(operation,api_key=credentials['apiKey'])
            progress('Saving published Model Asset ID')
            with connect(self.db) as db:
                db.execute('UPDATE character_component_records SET model_asset_id=?,published_revision=revision,pending_operation=\'\' WHERE kind=? AND id=?',(result.asset_id,kind,key))
                db.execute('INSERT INTO character_component_publications(kind,component_id,revision,asset_id,operation_path,published_at) VALUES(?,?,?,?,?,?)',
                           (kind,key,row['revision'],result.asset_id,result.operation_path,time.time()))
            self.export();return self._snapshot_row(self.get(kind,key))

    def export(self):
        data=self.snapshot();data.pop('atlas_families',None)
        target=self.root/'assets/manifests/character-components.json';target.parent.mkdir(parents=True,exist_ok=True)
        temp=target.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8');temp.replace(target)
