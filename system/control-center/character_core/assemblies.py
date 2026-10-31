"""Character recipes and dependency resolution; no FBX upload or animation ownership."""
import hashlib
import json
import math
import time
import uuid
from character_core.part_names import TOKEN
from sqlite_connection import connect
from character_core.rig_revisions import published_rig

BODY=('upper','lower','gloves','boots')
SLOTS=(*BODY,'head','eyes','eyebrows','hair')


def lua_table(value):
    if value is None:return 'nil'
    if isinstance(value,bool):return 'true' if value else 'false'
    if isinstance(value,(float,int)):return str(value)
    if isinstance(value,str):return json.dumps(value,ensure_ascii=False)
    if isinstance(value,list):return '{'+','.join(lua_table(x) for x in value)+'}'
    return '{'+','.join('['+lua_table(k)+']='+lua_table(v) for k,v in value.items())+'}'


class CharacterAssemblies:
    def __init__(self,root,characters,components):
        self.root=root;self.characters=characters;self.components=components;self.db=characters.db
        with connect(self.db) as db:
            columns={r[1] for r in db.execute('PRAGMA table_info(characters)')}
            if not {'visual_mode','assembly_json'} <= columns:
                backup=self.db.parent/'backups'/('before_character_assemblies_'+uuid.uuid4().hex+'.db')
                backup.parent.mkdir(exist_ok=True)
                with connect(backup) as target:db.backup(target)
                if 'visual_mode' not in columns:db.execute("ALTER TABLE characters ADD COLUMN visual_mode TEXT NOT NULL DEFAULT 'model'")
                if 'assembly_json' not in columns:db.execute("ALTER TABLE characters ADD COLUMN assembly_json TEXT NOT NULL DEFAULT '{}'")
            db.execute('''CREATE TABLE IF NOT EXISTS character_assembly_history(
                id INTEGER PRIMARY KEY,character_id TEXT NOT NULL,revision INTEGER NOT NULL,
                recipe_json TEXT NOT NULL,stats_json TEXT NOT NULL,changed_at REAL NOT NULL)''')
        characters.assemblies=self

    def resolve(self,recipe):
        missing=[];rig=published_rig(self.components,recipe['rig_id'],recipe.get('rig_revision'))
        if not rig:return dict(schema_version=1,ready=False,missing=['rig '+recipe['rig_id']])
        bones=json.loads(rig['metadata_json'])['bones']
        if not str(rig['model_asset_id']).isdigit():missing.append('rig '+rig['id'])
        result=dict(schema_version=1,rig=dict(id=rig['id'],asset_id=rig['model_asset_id'],
                    revision=rig['published_revision'],bone_names=[b['name'] for b in bones]),parts={})
        for slot in SLOTS:
            key=recipe['parts'].get(slot,'');row=self.components.get('part',key)
            if not row or row['rig_id']!=rig['id'] or row['slot']!=slot or row['role']!='part':
                missing.append(slot+': incompatible/missing '+key);continue
            if not str(row['model_asset_id']).isdigit():missing.append(slot+': '+key)
            try:meta=self.components.publication_metadata(row)
            except ValueError:
                missing.append(slot+': published bind metadata missing');continue
            atlas=self.components.atlases.binding('character_part',key)
            if atlas and not str(atlas.get('published_id') or '').isdigit():missing.append(slot+': atlas unpublished')
            roots=[b['name'] for b in meta.get('skeleton',[]) if not b['parent']]
            if not meta.get('attachment'):
                unknown=set(meta.get('used_bones',[]))-{b['name'] for b in bones}
                if unknown:missing.append(slot+': rig lacks bones '+', '.join(sorted(unknown)))
            result['parts'][slot]=dict(id=key,asset_id=row['model_asset_id'],revision=row['published_revision'],
                used_bones=meta.get('used_bones',[]),attachment=meta.get('attachment',''),
                socket_bone=roots[0] if meta.get('attachment') and len(roots)==1 else '',
                atlas_image_id=str(atlas['published_id'] or '') if atlas else '')
        result['ready']=not missing;result['missing']=missing
        result['fingerprint']=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()[:24]
        return result

    def decorate(self,row):
        recipe=json.loads(row['assembly_json']);resolved=self.resolve(recipe)
        row['assembly']=recipe;row['assembly_resolved']=resolved
        row['status']='ASSEMBLY_READY' if resolved['ready'] else 'ASSEMBLY_DRAFT'
        return row

    def save(self,payload):
        if not isinstance(payload,dict):raise ValueError('assembly payload must be an object')
        key=str(payload.get('id') or '').strip()
        if not TOKEN.fullmatch(key) or len(key)>64:raise ValueError('character id must be lower_case_snake_case')
        profile=str(payload.get('rig_id') or '');rig=self.components.get('rig',profile)
        if not rig:raise ValueError('select a registered rig')
        old=self.characters.get(key)
        if old and old.get('visual_mode')!='assembly':raise ValueError('this id belongs to a whole-model character; choose a new id')
        expected=payload.get('expected_revision',0)
        if expected!=(old['revision'] if old else 0):raise ValueError('character changed; refresh before saving')
        set_id=str(payload.get('set_id') or '')
        parts={}
        if set_id:
            if set_id not in self.components.snapshot()['sets']:raise ValueError('unknown starter set')
            for slot in BODY:
                row=self.components.get('part',set_id+'_'+slot)
                if row and row['rig_id']==profile:parts[slot]=row['id']
        supplied=payload.get('parts') or {}
        if not isinstance(supplied,dict) or set(supplied)-set(SLOTS):raise ValueError('unknown character slot')
        parts.update(supplied)
        if any(not isinstance(parts.get(s),str) or not parts[s] for s in SLOTS):raise ValueError('select all eight default parts')
        head=self.components.get('part',parts['head'])
        if not head or head['slot']!='head':raise ValueError('select a head')
        gender=head['gender']
        for slot,key_part in parts.items():
            part=self.components.get('part',key_part)
            if not part or part['rig_id']!=profile or part['slot']!=slot or part['role']!='part':raise ValueError(slot+': incompatible part')
            if part['gender'] not in {'common',gender}:raise ValueError(slot+': incompatible with selected head gender')
        recipe=dict(schema_version=1,rig_id=profile,set_id=set_id,parts=parts)
        previous_recipe=old.get('assembly',{}) if old else {}
        pin=payload.get('rig_revision',previous_recipe.get('rig_revision') if previous_recipe.get('rig_id')==profile else None)
        if pin is not None:
            selected=published_rig(self.components,profile,pin)
            if not selected:raise ValueError('published rig revision is unavailable')
            recipe['rig_revision']=pin;rig=selected
        else:
            rig=published_rig(self.components,profile) or rig
        stats=self.characters._validate_stats(payload,old)
        if not all(math.isfinite(v) for v in stats.values()):raise ValueError('starting stats must be finite')
        bones=json.loads(rig['metadata_json'])['bones']
        signature=rig['content_sha256'];resolved=self.resolve(recipe)
        with connect(self.db) as db:
            db.execute('BEGIN IMMEDIATE')
            current=db.execute('SELECT revision,visual_mode FROM characters WHERE id=?',(key,)).fetchone()
            if (current['revision'] if current else 0)!=expected or (current and current['visual_mode']!='assembly'):
                raise ValueError('character changed; refresh before saving')
            if old:db.execute('INSERT INTO character_assembly_history(character_id,revision,recipe_json,stats_json,changed_at) VALUES(?,?,?,?,?)',
                (key,old['revision'],old['assembly_json'],json.dumps(old['stats']),time.time()))
            db.execute('''INSERT INTO characters(id,display_name,race,gender,status,revision,created_at,updated_at,
                armature_name,bone_count,mesh_count,skeleton_signature,skeleton_structure_signature,skeleton_json,visual_mode,assembly_json)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                display_name=excluded.display_name,gender=excluded.gender,status=excluded.status,revision=excluded.revision,
                updated_at=excluded.updated_at,armature_name=excluded.armature_name,bone_count=excluded.bone_count,
                mesh_count=excluded.mesh_count,skeleton_signature=excluded.skeleton_signature,
                skeleton_structure_signature=excluded.skeleton_structure_signature,skeleton_json=excluded.skeleton_json,
                assembly_json=excluded.assembly_json''',
                (key,str(payload.get('display_name') or key)[:120],'human',gender,
                 'ASSEMBLY_READY' if resolved['ready'] else 'ASSEMBLY_DRAFT',expected+1,time.time(),time.time(),
                 profile+'_armature',len(bones),len(parts),signature,signature,
                 json.dumps({'bones':[dict(name=b['name'],parent=b['parent'],matrixLocal=b['matrix']) for b in bones]}),
                 'assembly',json.dumps(recipe)))
            for stat,value in stats.items():db.execute('INSERT OR REPLACE INTO character_stats VALUES(?,?,?)',(key,stat,value))
        self.characters.export();return self.snapshot()

    def snapshot(self):
        return dict(schema_version=1,items=[r for r in self.characters.list() if r.get('visual_mode')=='assembly'],
                    active_id=self.characters.active_id(),catalog=self.components.snapshot(),stats=self.characters.options())
