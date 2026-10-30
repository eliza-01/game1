"""Behavior tests for modular registration; no Roblox uploads or production DB."""
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'control-center'))
from character_core.components import CharacterComponents, ComponentConflict
from character_core.part_names import parse_part
from sqlite_connection import connect

IDENTITY=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]


class ComponentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'human.fbx';self.source.write_bytes(b'fbx fixture')
        self.info={'armature':'human_armature','bones':[dict(name='root',parent='',matrix=IDENTITY)],'parts':[]}
        self.names=['newborn_upper','newborn_gloves','head_01_male','eyes_01','eyebrows_01','hair_01_common']
        self.set_parts(self.names)
        self.store=CharacterComponents(self.root,analyzer=self.analyze)

    def set_parts(self,names):
        self.info['parts']=[dict(name=n,vertices=3,triangles=1,content_sha256=n+'hash',
            armature='human_armature',skeleton=self.info['bones'],used_bones=['root']) for n in names]

    def analyze(self,root,source,output=None):
        if output:
            Path(output).mkdir(parents=True,exist_ok=True)
            for name in ['rig',*(p['name'] for p in self.info['parts'])]:(Path(output)/(name+'.fbx')).write_bytes(name.encode())
        return copy.deepcopy(self.info)

    def register(self):
        plan=self.store.inspect(self.source);self.store.register(plan['token'],[]);return plan

    def published(self,key):
        with connect(self.store.db) as db:db.execute("UPDATE character_component_records SET model_asset_id='123',published_revision=revision WHERE id=?",(key,))

    def test_names_and_auto_set(self):
        plan=self.store.inspect(self.source)
        self.assertEqual(plan['new_sets'],['newborn']);self.assertEqual(self.store.snapshot()['items'],[])
        result=self.store.register(plan['token'],[])
        self.assertEqual(result['sets'],['newborn']);self.assertEqual(len(result['items']),7)
        self.assertEqual(parse_part('head_01_female')['gender'],'female')
        self.assertEqual(parse_part('hair_01_common')['gender'],'common')
        self.assertEqual(parse_part('eyes_01_spiral')['role'],'effect')
        for bad in ['Cube.001','newborn_boot','Head_01_male','head_00_male','head_01_common','../newborn_upper']:
            with self.assertRaises(ValueError):parse_part(bad)

    def test_published_requires_explicit_approval_and_preserves_id(self):
        self.register();self.published('newborn_upper')
        plan=self.store.inspect(self.source)
        self.assertEqual([p['id'] for p in plan['conflicts']],['newborn_upper'])
        with self.assertRaises(ComponentConflict):self.store.register(plan['token'],[])
        self.assertEqual(self.store.get('part','newborn_upper')['revision'],1)
        self.store.register(plan['token'],['newborn_upper'])
        row=self.store.get('part','newborn_upper')
        self.assertEqual(row['revision'],2);self.assertEqual(row['model_asset_id'],'123')
        self.assertEqual(row['published_revision'],1)
        self.store.register(plan['token'],['newborn_upper'])
        self.assertEqual(self.store.get('part','newborn_upper')['revision'],2)

    def test_partial_fbx_keeps_missing_parts_and_reuses_rig(self):
        self.register();self.published('newborn_upper');self.set_parts(['eyes_01'])
        plan=self.store.inspect(self.source);self.assertFalse(plan['conflicts'])
        self.store.register(plan['token'],[])
        self.assertEqual(self.store.get('part','newborn_upper')['model_asset_id'],'123')
        self.assertEqual(self.store.get('rig','human')['revision'],1)
        self.assertEqual(len(self.store.snapshot()['items']),7)

    def test_concurrent_inspection_cannot_override_new_revision(self):
        self.register();self.published('newborn_upper')
        a=self.store.inspect(self.source);b=self.store.inspect(self.source)
        self.store.register(a['token'],['newborn_upper'])
        with self.assertRaises(ComponentConflict):self.store.register(b['token'],['newborn_upper'])

    def test_incompatible_rig_rejected_before_any_registration(self):
        self.register();self.info['bones'][0]['matrix']=list(IDENTITY);self.info['bones'][0]['matrix'][3]=2
        with self.assertRaisesRegex(ValueError,'bind pose'):self.store.inspect(self.source)
        self.assertEqual(self.store.get('rig','human')['revision'],1)

    def test_publication_after_inspection_requires_new_approval(self):
        self.register();plan=self.store.inspect(self.source);self.published('newborn_upper')
        with self.assertRaisesRegex(ComponentConflict,'published after inspection'):
            self.store.register(plan['token'],[])

    def test_extraction_failure_leaves_catalog_unchanged(self):
        plan=self.store.inspect(self.source)
        original=self.store.analyze
        self.store.analyze=lambda *a: (_ for _ in ()).throw(ValueError('bad extraction'))
        with self.assertRaises(ValueError):self.store.register(plan['token'],[])
        self.assertEqual(self.store.snapshot()['items'],[])
        self.store.analyze=original;self.store.register(plan['token'],[])
        self.assertEqual(len(self.store.snapshot()['items']),7)

    def test_input_is_frozen_and_tampered_snapshot_rejected(self):
        plan=self.store.inspect(self.source);self.source.write_bytes(b'changed after picker')
        self.store.register(plan['token'],[])
        row=self.store.get('part','eyes_01')
        self.assertEqual((self.root/row['source_path']).read_bytes(),b'fbx fixture')
        p=self.store.inspect(self.source)
        (self.root/'.control-center/character-component-staging'/p['token']/'source.fbx').write_bytes(b'tampered')
        with self.assertRaises(ComponentConflict):self.store.register(p['token'],[])

    def test_atlas_reuses_shared_variant_with_revision_check(self):
        from PIL import Image
        self.register();image=self.root/'human_01_16x16_atlas.png';Image.new('RGB',(16,16)).save(image)
        variant=self.store.atlases.register_file(str(image))
        with connect(self.store.db) as db:db.execute("UPDATE texture_atlas_variants SET published_id='999',published_sha256=source_sha256 WHERE id=?",(variant['id'],))
        for key in ['newborn_upper','newborn_gloves']:self.store.bind_atlas(key,variant['id'],0)
        a=self.store.atlases.binding('character_part','newborn_upper');b=self.store.atlases.binding('character_part','newborn_gloves')
        self.assertEqual(a['published_id'],b['published_id']);self.assertEqual(a['published_id'],'999')
        with self.assertRaisesRegex(ValueError,'stale'):self.store.bind_atlas('newborn_upper',variant['id'],0)

    def test_publication_retry_polls_operation_and_does_not_upload_twice(self):
        self.register();credentials=dict(apiKey='fake',creatorType='user',creatorId='1')
        result=SimpleNamespace(asset_id='777',operation_path='operations/test',moderation_state='Approved')
        with patch('opencloud_assets.create_model_asset',return_value='operations/test') as upload,patch('opencloud_assets.wait_for_operation',side_effect=[TimeoutError('pending'),result]):
            with self.assertRaises(TimeoutError):self.store.publish('part','eyes_01',credentials)
            self.assertEqual(self.store.get('part','eyes_01')['pending_operation'],'operations/test')
            self.store.publish('part','eyes_01',credentials);self.store.publish('part','eyes_01',credentials)
            self.assertEqual(upload.call_count,1)
        self.assertEqual(self.store.get('part','eyes_01')['model_asset_id'],'777')

    def test_additive_migration_backup_and_legacy_untouched(self):
        with connect(self.store.db) as db:
            db.execute('CREATE TABLE characters(id TEXT PRIMARY KEY,model_asset_id TEXT)')
            db.execute("INSERT INTO characters VALUES('human_female','old_id')")
        CharacterComponents(self.root,analyzer=self.analyze)
        with connect(self.store.db) as db:self.assertEqual(db.execute('SELECT model_asset_id FROM characters').fetchone()[0],'old_id')
        self.assertEqual(len(list((self.root/'.control-center/backups').glob('before_character_components_*.db'))),1)

    def test_ui_controls_and_conflict_dialog_are_present(self):
        from html.parser import HTMLParser
        import re
        class Ids(HTMLParser):
            def __init__(self):super().__init__();self.ids=[]
            def handle_starttag(self,tag,attrs):
                self.ids.extend(v for k,v in attrs if k=='id' and v.startswith('cp-'))
        static=Path(__file__).resolve().parents[1]/'control-center/static'
        parser=Ids();parser.feed((static/'index.html').read_text(encoding='utf8'))
        references={'cp-'+key for key in re.findall(r"el\('([^']+)'\)",(static/'character-components.js').read_text(encoding='utf8'))}
        self.assertFalse(references-set(parser.ids),'missing bound controls')
        self.assertEqual(len(parser.ids),len(set(parser.ids)))

    def test_registration_survives_existing_startup_storage_migration(self):
        from source_only_assets import migrate_source_only_assets
        from sqlite_connection import ClosingConnection
        import sqlite3
        self.register()
        # Legacy migration uses raw sqlite contexts. Close its test-only handles
        # deterministically so Windows can remove the temporary database.
        original=sqlite3.connect
        with patch('source_only_assets.sqlite3.connect',side_effect=lambda *a,**kw:original(*a,factory=ClosingConnection,**kw)):
            self.assertIsNone(migrate_source_only_assets(self.root,self.store.db))
        for row in self.store.snapshot()['items']:
            self.assertTrue((self.root/row['prepared_path']).is_file())
            self.assertTrue(row['prepared_path'].replace('\\','/').startswith('assets/source/'))


if __name__=='__main__':unittest.main()
