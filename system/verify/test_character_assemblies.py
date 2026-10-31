"""Recipe registration/readiness over actual SQLite stores, without cloud uploads."""
import copy
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'control-center'))
from character_store import CharacterStore
from character_core.components import CharacterComponents
from character_core.assemblies import CharacterAssemblies
from sqlite_connection import connect,ClosingConnection


class AssemblyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        original=sqlite3.connect
        def closed(*args,**kwargs):kwargs.setdefault('factory',ClosingConnection);return original(*args,**kwargs)
        cleanup=patch('sqlite3.connect',side_effect=closed);cleanup.start();self.addCleanup(cleanup.stop)
        self.root=Path(self.temp.name);self.characters=CharacterStore(self.root)
        with connect(self.characters.db) as db:
            db.execute("INSERT INTO characters(id,display_name,race,gender,model_asset_id,status,created_at,updated_at) VALUES('human_female','Human Female','human','female','999','PUBLISHED',0,0)")
            db.execute("INSERT INTO project_settings VALUES('active_character_archetype_id','human_female')")
        bones=[dict(name='root',parent='',matrix=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1])]
        names=['newborn_upper','newborn_lower','newborn_gloves','newborn_boots','other_boots',
               'head_01_male','head_01_female','eyes_01','eyes_02','eyes_01_spiral','eyebrows_01',
               'hair_01_common','hair_01_male','hair_01_female']
        info=dict(armature='human_armature',bones=bones,parts=[dict(name=n,vertices=3,triangles=1,
            content_sha256=n,armature='human_armature',skeleton=bones,used_bones=['root']) for n in names])
        def analyzer(root,source,output=None):
            if output:
                output.mkdir(parents=True,exist_ok=True)
                for n in ['rig',*names]:(output/(n+'.fbx')).write_bytes(n.encode())
            return copy.deepcopy(info)
        self.components=CharacterComponents(self.root,analyzer=analyzer)
        source=self.root/'human.fbx';source.write_bytes(b'fixture')
        plan=self.components.inspect(source);self.components.register(plan['token'],[])
        self.assemblies=CharacterAssemblies(self.root,self.characters,self.components)

    def payload(self):
        return dict(id='human_male',display_name='Human Male',rig_id='human',set_id='newborn',expected_revision=0,
            parts=dict(head='head_01_male',eyes='eyes_01',eyebrows='eyebrows_01',hair='hair_01_common'))

    def publish_dependencies(self):
        with connect(self.characters.db) as db:
            db.execute("UPDATE character_component_records SET model_asset_id='123',published_revision=revision")

    def test_newborn_defaults_saved_without_upload_or_startup_change(self):
        self.assemblies.save(self.payload());row=self.characters.get('human_male')
        self.assertEqual(row['assembly']['parts']['gloves'],'newborn_gloves')
        self.assertEqual(row['gender'],'male');self.assertEqual(row['status'],'ASSEMBLY_DRAFT')
        self.assertEqual(len(row['assembly_resolved']['missing']),9)
        self.assertEqual(self.characters.active_id(),'human_female')
        self.assertEqual(self.characters.get('human_female')['model_asset_id'],'999')
        with self.assertRaises(ValueError):self.characters.set_active('human_male')

    def test_ready_assembly_can_be_startup_and_exports_runtime_recipe(self):
        self.assemblies.save(self.payload());self.publish_dependencies()
        self.characters.set_active('human_male')
        self.assertEqual(self.characters.runtime_selection()['mode'],'assembled')
        manifest=json.loads((self.root/'assets/manifests/character-archetypes.json').read_text(encoding='utf8'))
        row=next(r for r in manifest['archetypes'] if r['id']=='human_male')
        self.assertTrue(row['assembly']['ready']);self.assertIsNone(row['model']['assetId'])
        lua=(self.root/'src/shared/character/CharacterRegistry.luau').read_text(encoding='utf8')
        self.assertIn('visualMode = "assembly"',lua);self.assertIn('["fingerprint"]=',lua)

    def test_individual_clothing_override_and_shared_body_for_female_head(self):
        p=self.payload();p['id']='female_recipe';p['parts'].update(boots='other_boots',head='head_01_female')
        self.assemblies.save(p);row=self.characters.get(p['id'])
        self.assertEqual(row['gender'],'female');self.assertEqual(row['assembly']['parts']['boots'],'other_boots')
        self.assertEqual(row['assembly']['parts']['upper'],'newborn_upper')

    def test_gender_slot_effect_and_rig_validation(self):
        for field,value in [('hair','hair_01_female'),('eyes','eyes_01_spiral'),('head','newborn_upper')]:
            with self.subTest(field=field):
                p=self.payload();p['parts'][field]=value
                with self.assertRaises(ValueError):self.assemblies.save(p)
        p=self.payload();p['rig_id']='missing'
        with self.assertRaises(ValueError):self.assemblies.save(p)

    def test_legacy_collision_and_stale_edit_are_rejected(self):
        p=self.payload();p['id']='human_female'
        with self.assertRaises(ValueError):self.assemblies.save(p)
        self.assemblies.save(self.payload());p=self.payload();p['expected_revision']=1;p['parts']['eyes']='eyes_02'
        self.assemblies.save(p)
        with self.assertRaises(ValueError):self.assemblies.save(p)
        self.assertEqual(self.characters.get('human_male')['revision'],2)
        with connect(self.characters.db) as db:self.assertEqual(db.execute('SELECT count(*) FROM character_assembly_history').fetchone()[0],1)

    def test_nonfinite_stats_rejected(self):
        p=self.payload();p['stats']={'MaxHP':float('nan')}
        with self.assertRaises(ValueError):self.assemblies.save(p)
        self.assertIsNone(self.characters.get('human_male'))

    def test_staged_mesh_replacement_keeps_last_published_appearance(self):
        self.assemblies.save(self.payload());self.publish_dependencies()
        previous=self.components.get('part','eyes_01')
        with connect(self.characters.db) as db:
            db.execute('INSERT INTO character_component_history(kind,component_id,revision,record_json,changed_at) VALUES(?,?,?,?,?)',('part','eyes_01',1,json.dumps(previous),0))
            changed=json.loads(previous['metadata_json']);changed['used_bones']=['new_unpublished_bone']
            db.execute("UPDATE character_component_records SET revision=2,metadata_json=? WHERE id='eyes_01'",(json.dumps(changed),))
        row=self.characters.get('human_male')['assembly_resolved']
        self.assertTrue(row['ready']);self.assertEqual(row['parts']['eyes']['revision'],1)
        self.assertEqual(row['parts']['eyes']['used_bones'],['root'])

    def test_legacy_model_publisher_cannot_replace_a_recipe(self):
        self.assemblies.save(self.payload())
        with self.assertRaisesRegex(ValueError,'assembly editor'):self.characters.register({'existingId':'human_male'})
        with self.assertRaisesRegex(ValueError,'separately'):self.characters.publish('human_male',{})

    def test_migration_is_idempotent_and_preserves_legacy(self):
        CharacterAssemblies(self.root,self.characters,self.components)
        self.assertEqual(self.characters.get('human_female')['model_asset_id'],'999')
        self.assertEqual(len(list((self.root/'.control-center/backups').glob('before_character_assemblies_*.db'))),1)


    def stage_new_rig(self):
        from character_core.rig_revisions import stage_rig_revision
        rig=self.components.get('rig','human')
        bones=json.loads(rig['metadata_json'])['bones']
        bones.append(dict(name='face_eye_l',parent='root',matrix=bones[0]['matrix'][:]))
        artifact=self.root/'rig_revision.fbx';artifact.write_bytes(b'new rig fixture')
        return stage_rig_revision(self.components,'human',artifact,expected_revision=1,
            analyzer=lambda *a:dict(armature='human_armature',bones=bones,parts=[dict(name='rig_carrier')]))

    def test_rig_republication_pins_existing_character_and_preserves_live_asset(self):
        self.assemblies.save(self.payload());self.publish_dependencies()
        result=self.stage_new_rig()
        self.assertEqual(result['pinned_characters'],['human_male'])
        self.assertTrue(Path(result['backup']).is_file())
        row=self.characters.get('human_male')
        self.assertEqual(row['revision'],2)
        self.assertEqual(row['assembly']['rig_revision'],1)
        with connect(self.characters.db) as db:
            db.execute("UPDATE character_component_records SET model_asset_id='456',published_revision=revision WHERE kind='rig'")
        resolved=self.characters.get('human_male')['assembly_resolved']
        self.assertEqual(resolved['rig']['asset_id'],'123')
        self.assertEqual(resolved['rig']['bone_names'],['root'])
        self.assertTrue(resolved['ready'])

    def test_staged_rig_uses_published_metadata_before_upload(self):
        self.assemblies.save(self.payload());self.publish_dependencies();self.stage_new_rig()
        recipe=self.payload();self.assemblies.save({**recipe,'id':'second_recipe'})
        resolved=self.characters.get('second_recipe')['assembly_resolved']
        self.assertEqual(resolved['rig']['bone_names'],['root'])
        self.assertEqual(resolved['rig']['revision'],1)

    def test_edit_preserves_pin_and_switch_requires_explicit_available_revision(self):
        self.assemblies.save(self.payload());self.publish_dependencies();self.stage_new_rig()
        payload=self.payload();payload['expected_revision']=2
        self.assemblies.save(payload)
        self.assertEqual(self.characters.get('human_male')['assembly']['rig_revision'],1)
        payload['expected_revision']=3;payload['rig_revision']=99
        with self.assertRaisesRegex(ValueError,'unavailable'):self.assemblies.save(payload)
        recipe=self.characters.get('human_male')['assembly'];recipe['rig_revision']=99
        self.assertFalse(self.assemblies.resolve(recipe)['ready'])

    def test_unknown_part_bone_blocks_readiness(self):
        self.assemblies.save(self.payload());self.publish_dependencies()
        row=self.components.get('part','eyes_01');meta=json.loads(row['metadata_json']);meta['used_bones']=['removed_eye']
        with connect(self.characters.db) as db:db.execute("UPDATE character_component_records SET metadata_json=? WHERE kind='part' AND id='eyes_01'",(json.dumps(meta),))
        resolved=self.characters.get('human_male')['assembly_resolved']
        self.assertFalse(resolved['ready']);self.assertIn('rig lacks bones',str(resolved['missing']))


if __name__=='__main__':unittest.main()
