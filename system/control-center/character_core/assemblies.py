"""Character debug/startup recipes v2.

Armor is resolved through its logical set and explicit character gender. This
module never derives a set from geometry names and never owns atlas bindings.
"""
import hashlib
import json
import math
import time
import uuid
from character_core.part_names import TOKEN
from character_core.armor import ARMOR_SLOTS, GENDERS
from character_core.rig_revisions import published_rig
from character_core.part_names import hair_color_channels
import re
from sqlite_connection import connect

FACE = ('head', 'eye_l', 'eye_r', 'eyebrow_l', 'eyebrow_r', 'hair')
SOLID_FACE = frozenset(('eye_l', 'eye_r', 'eyebrow_l', 'eyebrow_r'))
HEX_COLOR = re.compile(r'#[0-9a-fA-F]{6}\Z')
MATERIAL_SLOTS = frozenset((*ARMOR_SLOTS,*FACE))
MATERIALS = frozenset(('Glass','Metal','SmoothPlastic','Plaster','Slate','Sandstone','Sand',
                       'Cardboard','Rubber','Limestone','Granite'))


def lua_table(value):
    if value is None: return 'nil'
    if isinstance(value,bool): return 'true' if value else 'false'
    if isinstance(value,(float,int)): return str(value)
    if isinstance(value,str): return json.dumps(value,ensure_ascii=False)
    if isinstance(value,list): return '{'+','.join(lua_table(x) for x in value)+'}'
    return '{'+','.join('['+lua_table(k)+']='+lua_table(v) for k,v in value.items())+'}'


class CharacterAssemblies:
    def __init__(self,root,characters,components,armor):
        self.root=root;self.characters=characters;self.components=components;self.armor=armor;self.db=characters.db
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

    def _part(self,slot,key,rig_id,gender,*,appearance_id=None):
        row=self.components.get('part',key)
        if not row or row['slot']!=slot or not self.components.part_compatible_with_rig(row,rig_id) or row['role']!='part':
            return None,'incompatible/missing mesh '+str(key)
        if gender not in json.loads(row['allowed_genders_json']):
            return None,'not compatible with '+gender
        if not str(row['model_asset_id']).isdigit() or row['published_revision']!=row['revision']:
            return None,'mesh not published/current'
        try:meta=self.components.publication_metadata(row)
        except ValueError:return None,'published bind metadata missing'
        atlas_id=''
        if appearance_id:
            try:
                appearance=self.armor.appearance(appearance_id)
                atlas=self.armor._atlas(appearance['atlas_variant_id'])
                if not atlas or not atlas['current'] or atlas['replacementPending']:
                    return None,'appearance texture not published/current'
                atlas_id=str(atlas['published_id'])
            except ValueError as exc:return None,str(exc)
        return dict(id=key,asset_id=row['model_asset_id'],revision=row['published_revision'],
                    mesh_family_id=row['mesh_family_id'],appearance_id=appearance_id or '',
                    used_bones=meta.get('used_bones',[]),attachment=meta.get('attachment',''),
                    attachment_mode=meta.get('attachment_mode','socket' if meta.get('attachment') else ''),
                    socket_bone=next((b['name'] for b in meta.get('skeleton',[]) if not b['parent']),''),
                    extras=[extra['name'] for extra in meta.get('extras',[])],
                    atlas_image_id=atlas_id),None

    def resolve(self,recipe):
        if recipe.get('schema_version')!=2:
            return dict(schema_version=2,ready=False,missing=['v1 assembly retired; save a new v2 recipe'],parts={})
        rig_id=recipe.get('rig_id') or ''
        gender=recipe.get('gender') or ''
        if gender not in GENDERS:
            return dict(schema_version=2,ready=False,missing=['explicit gender required'],parts={})
        rig=published_rig(self.components,rig_id,recipe.get('rig_revision'))
        if not rig:return dict(schema_version=2,ready=False,missing=['rig '+rig_id+' not published'],parts={})
        try:bones=json.loads(rig['metadata_json'])['bones']
        except (ValueError,KeyError):return dict(schema_version=2,ready=False,missing=['rig metadata unavailable'],parts={})
        result=dict(schema_version=2,rig=dict(id=rig['id'],asset_id=rig['model_asset_id'],
                    revision=rig['published_revision'],bone_names=[b['name'] for b in bones]),parts={})
        missing=[]
        selected_materials=recipe.get('part_materials') or {}
        if not isinstance(selected_materials,dict) or set(selected_materials)-MATERIAL_SLOTS or any(
                material not in MATERIALS for material in selected_materials.values()):
            return dict(schema_version=2,ready=False,missing=['invalid part material override'],parts={})
        if not str(rig['model_asset_id']).isdigit():missing.append('rig not published')
        armor_parts,armor_missing=self.armor.resolve(recipe.get('armor_set_id'),gender,rig_id)
        missing.extend('armor '+m for m in armor_missing)
        for slot,(mesh,appearance,_atlas) in armor_parts.items():
            record,problem=self._part(slot,mesh['id'],rig_id,gender,appearance_id=appearance['id'])
            if problem:missing.append(slot+': '+problem)
            else:
                if slot in selected_materials:record['material']=selected_materials[slot]
                result['parts'][slot]=record
        faces=recipe.get('face_parts') or {}
        for slot in FACE:
            selection=faces.get(slot) or {}
            key=selection.get('meshPartId') if isinstance(selection,dict) else None
            if not key:
                if slot=='head':missing.append('head: select a head MeshPart')
                continue
            record,problem=self._part(slot,key,rig_id,gender,
                appearance_id=None if slot in SOLID_FACE else selection.get('appearanceId'))
            if problem:missing.append(slot+': '+problem);continue
            mount=record['attachment_mode']
            if mount=='pivot':
                if slot!='hair' or record['attachment']!='hair_mount' or record['used_bones']:
                    missing.append('hair: invalid pivot attachment')
                if 'hair_mount' not in result['rig']['bone_names']:
                    missing.append('rig lacks hair_mount')
            elif mount not in ('','socket'):
                missing.append(slot+': unknown attachment mode')
            if not record['attachment']:
                unknown=set(record['used_bones'])-set(result['rig']['bone_names'])
                if unknown:missing.append(slot+': missing bones '+', '.join(sorted(unknown)))
            if slot == 'hair' and record['attachment_mode'] != 'pivot' and recipe.get('hair_colors'):
                missing.append('hair: color channels require rigid pivot hair')
            if slot == 'hair' and record['attachment_mode'] == 'pivot':
                try:
                    channels=hair_color_channels(dict(name=record['id'], extras=[{'name': n} for n in record['extras']]))
                    colors=recipe.get('hair_colors') or {}
                    if not isinstance(colors,dict) or set(colors)-set(channels):
                        raise ValueError('unexpected hair color channel')
                    if any(not isinstance(v,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',v) for v in colors.values()):
                        raise ValueError('hair color must be #RRGGBB')
                    record['colors']={k:v.upper() for k,v in colors.items()}
                except ValueError as exc:
                    missing.append('hair: '+str(exc))
            if slot in SOLID_FACE:
                color=(recipe.get('face_colors') or {}).get(slot)
                if color is not None:
                    if not isinstance(color,str) or not HEX_COLOR.fullmatch(color):
                        missing.append(slot+': color must be #RRGGBB')
                    else:
                        record['color']=color.upper()
            if slot in selected_materials:record['material']=selected_materials[slot]
            result['parts'][slot]=record
        result['ready']=not missing
        result['missing']=missing
        result['fingerprint']=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()[:24]
        return result

    def decorate(self,row):
        try:recipe=json.loads(row['assembly_json'])
        except (TypeError,ValueError):recipe={}
        resolved=self.resolve(recipe)
        row['assembly']=recipe;row['assembly_resolved']=resolved
        row['status']='ASSEMBLY_READY' if resolved['ready'] else 'ASSEMBLY_DRAFT'
        return row

    def save(self,payload):
        if not isinstance(payload,dict):raise ValueError('assembly payload must be an object')
        key=str(payload.get('id') or '').strip()
        if not TOKEN.fullmatch(key) or len(key)>64:raise ValueError('character id must be lower_case_snake_case')
        if payload.get('gender') not in GENDERS:raise ValueError('select male or female explicitly')
        rig_id=payload.get('rig_id')
        rig=self.components.get('rig',rig_id)
        if not rig:raise ValueError('select a registered rig')
        set_id=payload.get('armor_set_id')
        if not any(s['id']==set_id for s in self.armor.snapshot()['sets']):
            raise ValueError('select a registered armor set')
        old=self.characters.get(key)
        if old and old.get('visual_mode')!='assembly':raise ValueError('this id belongs to a whole-model character')
        expected=payload.get('expected_revision',0)
        if type(expected) is not int or expected!=(old['revision'] if old else 0):
            raise ValueError('character changed; refresh before saving')
        selected_materials=payload.get('part_materials') or {}
        if not isinstance(selected_materials,dict) or set(selected_materials)-MATERIAL_SLOTS or any(
                material not in MATERIALS for material in selected_materials.values()):
            raise ValueError('part_materials: unsupported body slot or Roblox material')
        faces=payload.get('face_parts') or {}
        if not isinstance(faces,dict) or set(faces)-set(FACE):raise ValueError('unknown face slot')
        face_atlases=payload.get('face_atlases') or {}
        if not isinstance(face_atlases,dict) or set(face_atlases)-{'head','hair'}:
            raise ValueError('atlases are available only for head and hair; eyes and eyebrows use colors')
        face_colors=payload.get('face_colors') or {}
        if not isinstance(face_colors,dict) or set(face_colors)-SOLID_FACE:
            raise ValueError('only eyes and eyebrows have solid face colors')
        for slot,color in face_colors.items():
            if not isinstance(color,str) or not HEX_COLOR.fullmatch(color):
                raise ValueError(slot+': color must be #RRGGBB')
            if not faces.get(slot):
                raise ValueError(slot+': choose a MeshPart before assigning a color')
        stored_faces={}
        for slot in FACE:
            part_id=faces.get(slot) or ''
            if part_id:
                row=self.components.get('part',part_id)
                if not row or row['slot']!=slot or not self.components.part_compatible_with_rig(row,rig_id) or payload['gender'] not in json.loads(row['allowed_genders_json']):
                    raise ValueError(slot+': incompatible MeshPart')
                variant=face_atlases.get(slot)
                appearance_id=self.armor.ensure_appearance(int(variant)) if variant not in ('',None) else None
                stored_faces[slot]=dict(meshPartId=part_id,appearanceId=appearance_id)
        if 'head' not in stored_faces:raise ValueError('select a compatible head')
        hair_colors=payload.get('hair_colors') or {}
        if not isinstance(hair_colors,dict):
            raise ValueError('hair_colors must be a channel-to-hex object')
        hair_id=stored_faces.get('hair',{}).get('meshPartId')
        if hair_colors and not hair_id:
            raise ValueError('select hair before assigning hair colors')
        if hair_id:
            hair_row=self.components.get('part',hair_id)
            hair_meta=json.loads(hair_row['metadata_json'])
            channels=hair_color_channels(hair_meta)
            if hair_colors and hair_meta.get('attachment_mode') != 'pivot':
                raise ValueError('hair color channels require rigid pivot hair')
            if set(hair_colors)-set(channels):
                raise ValueError('hair colors contain a channel not present in selected hair')
        for color in hair_colors.values():
            if not isinstance(color,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
                raise ValueError('hair colors must be #RRGGBB')
        recipe=dict(schema_version=2,rig_id=rig_id,gender=payload['gender'],armor_set_id=set_id,
                    face_parts=stored_faces,face_colors={k:v.upper() for k,v in face_colors.items()},
                    hair_colors={k:v.upper() for k,v in hair_colors.items()},
                    part_materials=selected_materials)
        pin=payload.get('rig_revision')
        if pin is not None:
            rig=published_rig(self.components,rig_id,pin)
            if not rig:raise ValueError('published rig revision unavailable')
            recipe['rig_revision']=pin
        else:rig=published_rig(self.components,rig_id) or rig
        stats=self.characters._validate_stats(payload,old)
        if not all(math.isfinite(v) for v in stats.values()):raise ValueError('starting stats must be finite')
        bones=json.loads(rig['metadata_json'])['bones']
        resolved=self.resolve(recipe)
        now=time.time()
        with connect(self.db) as db:
            db.execute('BEGIN IMMEDIATE')
            current=db.execute('SELECT revision,visual_mode FROM characters WHERE id=?',(key,)).fetchone()
            if (current['revision'] if current else 0)!=expected or (current and current['visual_mode']!='assembly'):
                raise ValueError('character changed; refresh before saving')
            if old:db.execute('''INSERT INTO character_assembly_history(character_id,revision,recipe_json,stats_json,changed_at)
                VALUES(?,?,?,?,?)''',(key,old['revision'],old['assembly_json'],json.dumps(old['stats']),now))
            db.execute('''INSERT INTO characters(id,display_name,race,gender,status,revision,created_at,updated_at,
                armature_name,bone_count,mesh_count,skeleton_signature,skeleton_structure_signature,skeleton_json,visual_mode,assembly_json)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                display_name=excluded.display_name,gender=excluded.gender,status=excluded.status,revision=excluded.revision,
                updated_at=excluded.updated_at,armature_name=excluded.armature_name,bone_count=excluded.bone_count,
                mesh_count=excluded.mesh_count,skeleton_signature=excluded.skeleton_signature,
                skeleton_structure_signature=excluded.skeleton_structure_signature,skeleton_json=excluded.skeleton_json,
                assembly_json=excluded.assembly_json''',
                (key,str(payload.get('display_name') or key)[:120],'human',payload['gender'],
                 'ASSEMBLY_READY' if resolved['ready'] else 'ASSEMBLY_DRAFT',expected+1,now,now,
                 rig_id+'_armature',len(bones),len(resolved['parts']),rig['content_sha256'],rig['content_sha256'],
                 json.dumps({'bones':[dict(name=b['name'],parent=b['parent'],matrixLocal=b['matrix']) for b in bones]}),
                 'assembly',json.dumps(recipe)))
            for stat,value in stats.items():db.execute('INSERT OR REPLACE INTO character_stats VALUES(?,?,?)',(key,stat,value))
        self.characters.export()
        return self.snapshot()

    def select_profile(self, character_id, purpose):
        """Select a *ready* v2 recipe. Studio admin and creation default are independent."""
        if purpose not in ('admin', 'default'):
            raise ValueError('profile purpose must be admin or default')
        row = self.characters.get(str(character_id or ''))
        if not row or row.get('visual_mode') != 'assembly' or (row.get('assembly') or {}).get('schema_version') != 2:
            raise ValueError('select a registered v2 character assembly')
        if not row['assembly_resolved']['ready']:
            raise ValueError('assembly is not ready: ' + '; '.join(row['assembly_resolved']['missing']))
        setting = 'studio_admin_assembly_id' if purpose == 'admin' else 'default_character_assembly_id'
        with connect(self.db) as db:
            db.execute('INSERT OR REPLACE INTO project_settings(key,value) VALUES(?,?)', (setting, row['id']))
        self.characters.export()
        return self.snapshot()

    def snapshot(self):
        catalog = self.components.snapshot()
        rig_ids = [row['id'] for row in catalog['items'] if row['kind'] == 'rig']
        for row in catalog['items']:
            if row['kind'] != 'part':
                continue
            source = self.components.get('part', row['id'])
            row['compatibleRigIds'] = [key for key in rig_ids
                                       if self.components.part_compatible_with_rig(source, key)]
        return dict(schema_version=2,items=[r for r in self.characters.list() if r.get('visual_mode')=='assembly'],
                    admin_id=self.characters.admin_id(),default_id=self.characters.active_id(),
                    catalog=catalog,armor=self.armor.snapshot(),stats=self.characters.options())
