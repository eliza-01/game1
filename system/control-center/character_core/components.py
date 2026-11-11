"""Character geometry registry v2. Existing archetypes/animation tables are untouched.

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
from character_core.part_names import parse_part, default_allowed_genders, rig_id, skeleton_matches, TOKEN, hair_color_channels, part_matches_source_rig, rig_family_and_gender
from character_core.component_fbx import inspect_fbx, inspect_rig_fbx

_LOCK=threading.RLock()


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for data in iter(lambda:f.read(1024*1024),b''):h.update(data)
    return h.hexdigest()


class ComponentConflict(ValueError):
    pass


class CharacterComponents:
    def __init__(self,root,*,analyzer=inspect_fbx,rig_analyzer=inspect_rig_fbx):
        self.root=Path(root).resolve();self.db=self.root/'.control-center/game1.db'
        self.db.parent.mkdir(parents=True,exist_ok=True);self.analyze=analyzer;self.analyze_rig=rig_analyzer
        # Online backup before the first additive migration; safe with WAL.
        with connect(self.db) as db:
            exists=db.execute("SELECT 1 FROM sqlite_master WHERE name='character_component_schema'").fetchone()
            if not exists:
                backup=self.db.parent/'backups'/('before_character_components_'+uuid.uuid4().hex+'.db')
                backup.parent.mkdir(exist_ok=True)
                with connect(backup) as target:db.backup(target)
            db.executescript('''
                CREATE TABLE IF NOT EXISTS character_component_schema(version INTEGER PRIMARY KEY);
                INSERT OR IGNORE INTO character_component_schema VALUES(2);
                CREATE TABLE IF NOT EXISTS character_component_records(
                    kind TEXT NOT NULL,id TEXT NOT NULL,rig_id TEXT NOT NULL,slot TEXT NOT NULL,
                    set_id TEXT NOT NULL DEFAULT '',gender TEXT NOT NULL DEFAULT 'common',role TEXT NOT NULL,
                    revision INTEGER NOT NULL,content_sha256 TEXT NOT NULL,source_path TEXT NOT NULL,
                    prepared_path TEXT NOT NULL,prepared_sha256 TEXT NOT NULL,metadata_json TEXT NOT NULL,
                    model_asset_id TEXT NOT NULL DEFAULT '',published_revision INTEGER NOT NULL DEFAULT 0,
                    pending_operation TEXT NOT NULL DEFAULT '',created_at REAL NOT NULL,
                    PRIMARY KEY(kind,id));
                CREATE TABLE IF NOT EXISTS character_mesh_families(
                    id TEXT PRIMARY KEY,rig_profile_id TEXT NOT NULL,created_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS character_component_imports(
                    id TEXT PRIMARY KEY,plan_json TEXT NOT NULL,committed INTEGER NOT NULL DEFAULT 0,created_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS character_component_history(
                    id INTEGER PRIMARY KEY,kind TEXT NOT NULL,component_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,record_json TEXT NOT NULL,changed_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS character_component_publications(
                    id INTEGER PRIMARY KEY,kind TEXT NOT NULL,component_id TEXT NOT NULL,revision INTEGER NOT NULL,
                    asset_id TEXT NOT NULL,operation_path TEXT NOT NULL,published_at REAL NOT NULL);
            ''')
        with connect(self.db) as db:
            columns={r['name'] for r in db.execute('PRAGMA table_info(character_component_records)')}
            if 'mesh_family_id' not in columns:
                db.execute("ALTER TABLE character_component_records ADD COLUMN mesh_family_id TEXT NOT NULL DEFAULT ''")
            if 'allowed_genders_json' not in columns:
                db.execute("ALTER TABLE character_component_records ADD COLUMN allowed_genders_json TEXT NOT NULL DEFAULT '[]'")
            db.execute('DELETE FROM character_component_schema WHERE version<>2')
            db.execute('INSERT OR IGNORE INTO character_component_schema VALUES(2)')
        self.atlases=AtlasRegistry(self.root)

    def get(self,kind,key):
        if kind not in {'rig','part'}:raise ValueError('invalid component kind')
        with connect(self.db) as db:
            row=db.execute('SELECT * FROM character_component_records WHERE kind=? AND id=?',(kind,key)).fetchone()
        return dict(row) if row else None

    def part_compatible_with_rig(self, part, target_rig_id):
        """Cross-rig reuse is safe only for common geometry with matching bind pose.

        Allowed genders describe an item in the game, but do not guarantee
        its skin weights fit an unrelated Armature. Compare the *published*
        bones, never trust a name or a pending revision.
        """
        if part['rig_id'] == target_rig_id:
            return True
        if part['gender'] != 'common':
            return False
        try:
            source_family, _ = rig_family_and_gender(part['rig_id'])
            target_family, _ = rig_family_and_gender(target_rig_id)
            if source_family != target_family:
                return False
            source = self.get('rig', part['rig_id'])
            target = self.get('rig', target_rig_id)
            if not source or not target:
                return False
            a = self.publication_metadata(source)['bones']
            b = self.publication_metadata(target)['bones']
            skeleton_matches(a, b)
            return True
        except (ValueError, KeyError, TypeError):
            return False

    def _snapshot_row(self,row):
        row=dict(row);row['metadata']=json.loads(row.pop('metadata_json'))
        row['allowedGenders']=json.loads(row.pop('allowed_genders_json'))
        row['status']='published' if row['published_revision']==row['revision'] else ('replacement_pending' if row['model_asset_id'] else 'registered')
        # Appearance is owned by ArmorCatalog, never bound to geometry directly.
        row['atlas']=None
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
            families=[dict(r) for r in db.execute('SELECT * FROM character_mesh_families ORDER BY id')]
        return dict(schema_version=2,items=[self._snapshot_row(r) for r in rows],mesh_families=families,
                    atlas_families=self.atlases.catalog(domain='character'))

    def inspect(self,source):
        # Freeze the bytes selected by the native picker. A later user edit cannot
        # silently change what is committed after the confirmation dialog.
        ident=uuid.uuid4().hex
        directory=self.root/'.control-center/character-component-staging'/ident
        directory.mkdir(parents=True);frozen=directory/'source.fbx'
        shutil.copy2(Path(source).resolve(),frozen)
        try:
            # A broken/unrecognized part must not hide a changed primary rig.
            # Retry only the armature inspection; never silently accept those parts.
            part_error = ''
            try:
                info=self.analyze(self.root,frozen)
            except ValueError as exc:
                part_error=str(exc)
                try:
                    info=self.analyze_rig(self.root,frozen)
                except Exception:
                    raise exc  # Preserve the original detailed FBX failure.
            key=rig_id(info['armature'])
            rig_in_source=info.get('rig_present', True)
            if not rig_in_source:
                # A rigless rigid hair FBX does not carry a bind skeleton. Prefer
                # the matching gendered rig if present, then an existing shared
                # family rig. A common hair may target the only existing
                # gendered rig, but never pick arbitrarily between two.
                existing_rig=self.get('rig',key)
                if not existing_rig:
                    family, specific_gender = rig_family_and_gender(key)
                    candidates=([family] if specific_gender else
                                [family+'_male',family+'_female'])
                    available=[candidate for candidate in candidates if self.get('rig',candidate)]
                    if len(available) == 1:
                        key=available[0]
                        info['armature']=key+'_armature'
                        existing_rig=self.get('rig',key)
                    elif len(available) > 1:
                        raise ValueError('rigless common hair matches multiple rig profiles; '
                                         'include the intended Armature in the FBX')
                if not existing_rig:
                    raise ValueError(key + ': register a compatible primary rig before importing standalone hair')
                saved_bones=json.loads(existing_rig['metadata_json'])['bones']
                if 'hair_mount' not in {bone['name'] for bone in saved_bones}:
                    raise ValueError(key + ': registered rig has no hair_mount')
                info['bones']=saved_bones
            for bone in info['bones']:
                if not TOKEN.fullmatch(bone['name']) or len(bone['matrix'])!=16 or not all(math.isfinite(v) for v in bone['matrix']):
                    raise ValueError('bone names must be lower_case_snake_case with finite bind matrices')
            old=self.get('rig',key)
            rig_changed = False
            rig_difference = ''
            if old:
                try:
                    skeleton_matches(json.loads(old['metadata_json'])['bones'], info['bones'])
                except ValueError as exc:
                    rig_changed = True
                    rig_difference = str(exc).split('; register a new')[0]
                if rig_changed and old['published_revision'] not in (0, old['revision']):
                    raise ComponentConflict('publish the pending rig revision before replacing it again')
            # Inspect valid components independently. An unrelated rejected mesh
            # must not make a correctly authored rigid hairstyle disappear.
            part_errors=list(info.get('part_errors') or []) if not part_error else []
            parts=[]
            seen=set()
            if not part_error:
                for part in info['parts']:
                    try:
                        for bone in part['skeleton']:
                            if not TOKEN.fullmatch(bone['name']) or len(bone['matrix'])!=16 or not all(math.isfinite(v) for v in bone['matrix']):
                                raise ValueError('bone names must be lower_case_snake_case with finite bind matrices')
                        meta=parse_part(part['name'])
                        if not part_matches_source_rig(meta, key):
                            raise ValueError(
                                f"{part['name']}: incompatible with {key}_armature; "
                                "mesh family and gender must match the source rig"
                            )
                        if meta['id'] in seen:
                            raise ValueError('duplicate mesh names: '+meta['id'])
                        if part.get('extras'):
                            if meta['slot'] != 'hair' or part.get('attachment_mode') != 'pivot':
                                raise ValueError(part['name'] + ': extras require rigid pivot hair')
                            hair_color_channels(part)
                        if part.get('attachment_mode') == 'pivot':
                            if (meta['slot'] != 'hair' or part.get('attachment') != 'hair_mount'
                                    or part.get('armature') or part.get('skeleton') or part.get('used_bones')):
                                raise ValueError(part['name']+': invalid rigid hair pivot attachment')
                            if not any(b['name']=='hair_mount' for b in info['bones']):
                                raise ValueError('rigid hair requires hair_mount in primary rig')
                        parts.append({**part,**meta,'rig_id':key, 'allowed_genders':default_allowed_genders(meta)})
                        seen.add(meta['id'])
                    except ValueError as exc:
                        part_errors.append(dict(name=part.get('name',''),message=str(exc)))
            if part_error:
                part_errors.insert(0,dict(name='',message=part_error))
            part_error='; '.join(error['message'] for error in part_errors)
            # With no valid components, only a changed, registered rig may be
            # inspected. Preserve the strict error for all other cases.
            if not parts and part_error and (not old or not rig_changed):
                raise ValueError(part_error)
            if not parts and not part_error:
                raise ValueError('FBX has no parts')
            rig_only_required=bool(part_error and not parts)
            partial_required=bool(part_error and parts)
            rows=[]
            for p in parts:
                old_part=self.get('part',p['id'])
                if old_part and old_part['rig_id']!=key:raise ValueError(p['id']+': belongs to another rig')
                rows.append(dict(id=p['id'],slot=p['slot'],mesh_family_id=p['mesh_family_id'],
                    allowedGenders=json.loads(old_part['allowed_genders_json']) if old_part else p['allowed_genders'],role=p['role'],
                    attachment_mode=p.get('attachment_mode',''),extras=p.get('extras',[]),
                    vertices=p['vertices'],triangles=p['triangles'],
                    normalized_vertices=p.get('normalized_vertices',0),
                    existing_revision=old_part['revision'] if old_part else 0,
                    published_asset_id=old_part['model_asset_id'] if old_part else '',
                    content_unchanged=bool(old_part and old_part['content_sha256']==p['content_sha256'])))
            plan=dict(schema_version=2,rig_in_source=rig_in_source,token=ident,source=str(frozen.relative_to(self.root)),sha256=sha(frozen),
                rig_id=key,bones=info['bones'],armature=info['armature'],parts=parts,rows=rows,
                rig_revision=old['revision'] if old else 0,
                rig_published_asset_id=old['model_asset_id'] if old else '',
                rig_changed=rig_changed,rig_difference=rig_difference,
                rig_only_required=rig_only_required,partial_required=partial_required,
                part_error=part_error,part_errors=part_errors)
            with connect(self.db) as db:
                db.execute('INSERT INTO character_component_imports(id,plan_json,created_at) VALUES(?,?,?)',
                           (ident,json.dumps(plan),time.time()))
            return dict(schema_version=2,token=ident,rig_id=key,bone_count=len(info['bones']),parts=rows,
                conflicts=[p for p in rows if p['published_asset_id']],
                registered=[p for p in rows if p['existing_revision']],
                rig_only_required=rig_only_required,partial_required=partial_required,
                part_error=part_error,part_errors=part_errors,
                rig=dict(id=key,existing_revision=old['revision'] if old else 0,
                         published_asset_id=old['model_asset_id'] if old else '',
                         changed=rig_changed,warning=rig_difference))
        except Exception:
            shutil.rmtree(directory)
            raise

    def register(self,token,replacements,*,replace_rig=False,rig_only=False,allow_partial=False,new_parts=None,compatibility=None):
        with _LOCK:
            with connect(self.db) as db:
                saved=db.execute('SELECT * FROM character_component_imports WHERE id=?',(token,)).fetchone()
            if not saved:raise ValueError('unknown inspection; choose FBX again')
            if saved['committed']:return self.snapshot()
            plan=json.loads(saved['plan_json']);frozen=self.root/plan['source']
            if not frozen.is_file() or sha(frozen)!=plan['sha256']:raise ComponentConflict('inspection source changed; choose FBX again')
            if type(rig_only) is not bool or (rig_only and not plan.get('rig_changed')):
                raise ComponentConflict('rig-only replacement requires an inspected rig change')
            if plan.get('rig_only_required') and not rig_only:
                raise ComponentConflict('rig-only registration is required: FBX components failed validation')
            if type(allow_partial) is not bool or (plan.get('partial_required') and not rig_only and not allow_partial):
                raise ComponentConflict('explicit approval is required to register only the valid FBX parts')
            # An FBX is a container of candidate parts, NOT a batch replacement.
            # New components are selected independently from registered components.
            # For older clients, omitted newParts still means all new components.
            existing={p['id'] for p in plan['rows'] if p['existing_revision']}
            new={p['id'] for p in plan['rows'] if not p['existing_revision']}
            if (not isinstance(replacements,list) or any(not isinstance(v,str) for v in replacements)
                    or len(replacements)!=len(set(replacements)) or not set(replacements)<=existing):
                raise ComponentConflict('replacement approval contains unknown or duplicate registered parts')
            if new_parts is None:
                new_parts=sorted(new) if not rig_only else []
            if (not isinstance(new_parts,list) or any(not isinstance(v,str) for v in new_parts)
                    or len(new_parts)!=len(set(new_parts)) or not set(new_parts)<=new):
                raise ComponentConflict('new component selection contains unknown or duplicate parts')
            if rig_only and (replacements or new_parts):
                raise ComponentConflict('rig-only registration cannot modify mesh components')
            approved_replacements=set(replacements)
            approved_new=set(new_parts)
            from character_core.armor import gender_pair
            if compatibility is None: compatibility={}
            if not isinstance(compatibility,dict) or set(compatibility)-{p['id'] for p in plan['rows']}:
                raise ComponentConflict('unknown part in gender compatibility selection')
            inspected_allowed={p['id']:p['allowedGenders'] for p in plan['rows']}
            allowed_by_id={p['id']:gender_pair(compatibility.get(p['id'],inspected_allowed[p['id']]))
                           for p in plan['parts']}
            if type(replace_rig) is not bool or replace_rig != bool(plan.get('rig_changed')):
                raise ComponentConflict('explicit Replace Rig approval is required when bind pose, parent or bone set changes')
            def validate(db):
                for kind,key,revision in [('rig',plan['rig_id'],plan['rig_revision']),
                    *(('part',p['id'],p['existing_revision']) for p in ([] if rig_only else plan['rows']))]:
                    row=db.execute('SELECT revision,pending_operation,model_asset_id FROM character_component_records WHERE kind=? AND id=?',(kind,key)).fetchone()
                    if (row['revision'] if row else 0)!=revision or (row and row['pending_operation']):
                        raise ComponentConflict('catalog changed or publication pending; inspect FBX again')
                    if kind=='rig' and (row['model_asset_id'] if row else '')!=plan.get('rig_published_asset_id',''):
                        raise ComponentConflict('rig was published after inspection; inspect FBX again')
                    if kind=='part':
                        inspected=next(p for p in plan['rows'] if p['id']==key)
                        if (row['model_asset_id'] if row else '')!=inspected['published_asset_id']:
                            raise ComponentConflict('part was published after inspection; inspect FBX again')
            with connect(self.db) as db:validate(db)
            if not (approved_replacements or approved_new or (replace_rig and plan.get('rig_changed'))):
                raise ComponentConflict('nothing selected; choose new components or approve replacements')
            folder=self.root/'assets/source/character_components/imports'/token
            # game1 is source-only: startup migrates/removes assets/prepared.
            # Extracted component FBX files are canonical publication inputs.
            prepared=self.root/'assets/source/character_components'/token
            folder.mkdir(parents=True,exist_ok=True);shutil.copy2(frozen,folder/'source.fbx')
            # When part validation failed, export the rig carrier only. Other
            # components cannot be extracted/registered by this inspected plan.
            if plan.get('rig_only_required'):
                info=self.analyze_rig(self.root,folder/'source.fbx',prepared)
            else:
                info=self.analyze(self.root,folder/'source.fbx',prepared)
            if info.get('rig_present', True) != plan.get('rig_in_source', True):
                raise ComponentConflict('FBX rig presence changed during extraction')
            if plan.get('rig_in_source', True):
                skeleton_matches(plan['bones'],info['bones'])
            if not rig_only:
                expected={p['name']:p['content_sha256'] for p in plan['parts']}
                actual={p['name']:p['content_sha256'] for p in info['parts'] if p['name'] in expected}
                if (actual!=expected or len(actual)!=len(expected)
                        or info.get('part_errors',[])!=plan.get('part_errors',[])[:len(info.get('part_errors',[]))]):
                    raise ComponentConflict('FBX changed during extraction')
            entries=[('rig',plan['rig_id'],dict(bones=plan['bones'],armature=plan['armature']),None)] if plan.get('rig_in_source', True) else []
            if not rig_only:
                selected_parts=approved_replacements | approved_new
                entries.extend(('part',p['id'],p,p) for p in plan['parts'] if p['id'] in selected_parts)
            with connect(self.db) as db:
                db.execute('BEGIN IMMEDIATE');validate(db)
                for kind,key,meta,part in entries:
                    old=db.execute('SELECT * FROM character_component_records WHERE kind=? AND id=?',(kind,key)).fetchone()
                    if old and kind=='rig' and not plan.get('rig_changed'):continue # compatible rig is reused
                    content=part['content_sha256'] if part else hashlib.sha256(json.dumps(plan['bones'],sort_keys=True).encode()).hexdigest()
                    if old and old['content_sha256']==content and key not in approved_replacements:continue
                    artifact=prepared/((key if part else 'rig')+'.fbx')
                    if not artifact.is_file() or artifact.stat().st_size==0:raise ValueError('missing extracted FBX: '+key)
                    if old:
                        db.execute('INSERT INTO character_component_history(kind,component_id,revision,record_json,changed_at) VALUES(?,?,?,?,?)',
                            (kind,key,old['revision'],json.dumps(dict(old)),time.time()))
                    revision=old['revision']+1 if old else 1
                    if part and part['mesh_family_id']:
                        family=part['mesh_family_id']
                        family_row=db.execute('SELECT rig_profile_id FROM character_mesh_families WHERE id=?',(family,)).fetchone()
                        if family_row and family_row['rig_profile_id'] != plan['rig_id']:
                            raise ComponentConflict(family+': mesh family already belongs to another rig profile')
                        db.execute('INSERT OR IGNORE INTO character_mesh_families(id,rig_profile_id,created_at) VALUES(?,?,?)',
                                   (family,plan['rig_id'],time.time()))
                    db.execute('''INSERT INTO character_component_records
                        (kind,id,rig_id,slot,set_id,gender,role,revision,content_sha256,source_path,prepared_path,prepared_sha256,metadata_json,created_at,mesh_family_id,allowed_genders_json)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(kind,id) DO UPDATE SET
                        revision=excluded.revision,content_sha256=excluded.content_sha256,source_path=excluded.source_path,
                        prepared_path=excluded.prepared_path,prepared_sha256=excluded.prepared_sha256,metadata_json=excluded.metadata_json,
                        mesh_family_id=excluded.mesh_family_id,allowed_genders_json=excluded.allowed_genders_json''',
                        (kind,key,plan['rig_id'],part['slot'] if part else 'rig',part['set_id'] if part else '',
                         part['gender'] if part else 'common',part['role'] if part else 'core',revision,content,
                         str((folder/'source.fbx').relative_to(self.root)),str(artifact.relative_to(self.root)),sha(artifact),json.dumps(meta),time.time(),
                         part['mesh_family_id'] if part else '',json.dumps(allowed_by_id[part['id']]) if part else '[]'))
                db.execute('UPDATE character_component_imports SET committed=1 WHERE id=?',(token,))
            self.export()
            return self.snapshot()

    def set_compatibility(self,key,allowed,expected):
        """Metadata-only authoring: changing gender NEVER changes Mesh publication revision."""
        from character_core.armor import gender_pair
        allowed=gender_pair(allowed)
        # Existing pre-v2 components have an unassigned compatibility ([]).
        # It is a valid optimistic-lock baseline, but never a valid new value.
        if expected != []:
            expected=gender_pair(expected)
        with connect(self.db) as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute("SELECT * FROM character_component_records WHERE kind='part' AND id=?",(key,)).fetchone()
            if not row:raise ValueError('unknown character part')
            if json.loads(row['allowed_genders_json']) != expected:
                raise ComponentConflict('gender compatibility changed; refresh first')
            db.execute("UPDATE character_component_records SET allowed_genders_json=? WHERE kind='part' AND id=?",
                       (json.dumps(allowed),key))
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
