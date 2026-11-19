"""M370 · published NPC texture reuse without Open Cloud publication or Studio writes."""
from __future__ import annotations

import hashlib
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / 'control-center'
sys.path.insert(0, str(ROOT))

from monster_store import MonsterStore, NPC_PUBLICATION_PIPELINE
from services.texture_atlas_registry import AtlasRegistry
from services.npc_atlas_sources import NpcAtlasSources
from services.studio_asset_sync import StudioAssetSyncService
from api import read_catalog, write_actors


class StoreStub:
    def __init__(self, rows):
        self.rows = rows
    def list(self):
        return self.rows


class LocationStub(StoreStub):
    def __init__(self, rows, atlases):
        super().__init__(rows)
        self.atlases = atlases


class NpcAtlasReuseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='game1-m370-atlas-')
        self.root = Path(self.temp.name)
        self.npcs = MonsterStore(self.root,kind='npc')
        self.monsters = MonsterStore(self.root,kind='monster')
        self.atlases = AtlasRegistry(self.root)
        self.npcs.atlases = self.atlases
        self.npcs.export()
        for store, slug in ((self.npcs,'target'),(self.monsters,'source')):
            with store.connect() as db:
                db.execute('''INSERT INTO monsters(slug,name_en,model_source_path,model_sha256,model_asset_id,
                    model_published_sha256,publication_pipeline,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?)''',(slug,slug,'assets/source/actors/rig.fbx',
                    'modelhash','1234','modelhash',NPC_PUBLICATION_PIPELINE,1,1))
        model = self.root/'assets/source/actors/rig.fbx'
        model.parent.mkdir(parents=True,exist_ok=True)
        model.write_bytes(b'fbx-model-placeholder')
        from PIL import Image
        filename = self.root/'assets/source/monsters/source/textures/source_4x4_atlas.png'
        filename.parent.mkdir(parents=True,exist_ok=True)
        Image.new('RGBA',(4,4),(100,30,25,200)).save(filename)
        self.relative = filename.relative_to(self.root).as_posix()
        self.sha = hashlib.sha256(filename.read_bytes()).hexdigest()
        with self.monsters.connect() as db:
            db.execute('''INSERT INTO monster_textures(id,monster_slug,slot,source_path,prepared_path,
                sha256,asset_id,published_sha256,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)''',('source__atlas','source','atlas',self.relative,
                self.relative,self.sha,'9988776655',self.sha,1,1))
        self.weapons = StoreStub([{'slug':'blade','name_en':'Blade','textures':[
            {'slot':'blade','asset_id':'123456','source_path':self.relative,'sha256':self.sha,
             'published_sha256':self.sha}]}])
        self.location = LocationStub([{'slug':'flower','name_en':'Flower','atlasVariantId':None,
            'texture_asset_id':'333333','texture_path':self.relative,'texture_sha256':self.sha,
            'texture_published_sha256':self.sha}],self.atlases)
        self.houses = StoreStub([{'slug':'hut','name_en':'Hut','textures':{'house':{
            'assetId':'444444','path':self.relative,'sha256':self.sha,'publishedSha256':self.sha}}}])
        self.service = NpcAtlasSources(self.npcs,self.monsters,self.weapons,self.location,self.houses)

    def tearDown(self):
        self.temp.cleanup()

    def _select(self,kind='monster',slug='source',slot='atlas',revision=0,variant_id=0):
        return self.service.connect({'npcSlug':'target','sourceKind':kind,'sourceSlug':slug,
            'sourceSlot':slot,'variantId':variant_id,'sourceImageId':
            next((r['imageId'] for r in self.service.snapshot()['groups'][kind] if r['slug']==slug and r['slot']==slot and r['variantId']==variant_id),'0')
            if kind in self.service.GROUPS else '', 'expectedRevision':revision})

    def test_all_five_categories_and_no_private_paths(self):
        groups = self.service.snapshot()['groups']
        self.assertEqual(list(groups),['npc','monster','weapon','location_asset','real_estate'])
        self.assertEqual([len(groups[c]) for c in groups],[0,1,1,1,1])
        self.assertEqual(groups['monster'][0]['imageId'],'9988776655')
        self.assertNotIn('sourcePath',groups['monster'][0])
        self.assertNotIn('sha256',groups['monster'][0])

    def test_one_time_index_and_binding_without_image_republication(self):
        with patch('monster_store.create_image_asset',side_effect=AssertionError('unexpected upload')):
            row = self._select()
            self.assertEqual(row['atlas_binding']['published_id'],'9988776655')
            self.assertTrue(row['atlas_binding']['current'])
            self.assertEqual(row['atlas_binding']['revision'],1)
            self.assertIn('9988776655',(self.root/'src/shared/npc/NpcRegistry.luau').read_text(encoding='utf-8'))
            self.assertEqual(len(self.atlases.catalog()),1)
            # Selecting the identical source does not create a second shared atlas.
            self._select(revision=1)
            self.assertEqual(len(self.atlases.catalog()[0]['variants']),1)
            self.assertEqual(self.npcs.publish('target',{'description':'test'})['atlas_binding']['published_id'],'9988776655')
            self.assertEqual(len(self.atlases.catalog()[0]['variants']),1)

    def test_selection_conflict_rejected_and_preserves_binding(self):
        self._select()
        with self.assertRaisesRegex(ValueError,'stale atlas binding revision'):
            self._select(revision=0)
        self.assertEqual(self.npcs.get('target')['atlas_binding']['published_id'],'9988776655')

    def test_stale_publication_rejected_without_mutating_existing_selection(self):
        self._select()
        with self.monsters.connect() as db:
            db.execute("UPDATE monster_textures SET published_sha256='different' WHERE monster_slug='source'")
        with self.assertRaisesRegex(ValueError,'no longer exists'):
            self._select(revision=1)
        self.assertEqual(self.npcs.get('target')['atlas_binding']['published_id'],'9988776655')

    def test_indexed_image_reusable_when_old_local_source_was_removed(self):
        self._select()
        self.service.clear({'npcSlug':'target'})
        (self.root/self.relative).unlink()
        with patch.object(self.atlases,'index_existing_published_image',
                          side_effect=AssertionError('should reuse indexed image')):
            self.assertEqual(self._select()['atlas_binding']['published_id'],'9988776655')

    def test_unknown_category_and_npc_rejected(self):
        with self.assertRaisesRegex(ValueError,'source category'):
            self._select('wrong','source','atlas')
        with self.assertRaisesRegex(ValueError,'target NPC'):
            self.service.connect({'npcSlug':'missing','sourceKind':'monster','sourceSlug':'source','sourceSlot':'atlas','sourceImageId':'9988776655'})

    def test_clear_unbinds_only_npc_and_does_not_delete_shared_variant(self):
        self._select()
        self.service.clear({'npcSlug':'target'})
        self.assertIsNone(self.npcs.get('target').get('atlas_binding'))
        self.assertEqual(len(self.atlases.catalog()[0]['variants']),1)
        self.assertNotIn('9988776655',(self.root/'src/shared/npc/NpcRegistry.luau').read_text(encoding='utf-8'))

    def test_existing_variant_can_be_selected_from_another_domain(self):
        published = self._select()
        variant = published['atlas_binding']['variant_id']
        self.location.rows[0]['atlasVariantId'] = variant
        selected = self._select('location_asset','flower','atlas',1,variant)
        self.assertEqual(selected['atlas_binding']['published_id'],'9988776655')
        self.assertEqual(len(self.atlases.catalog()[0]['variants']),1)

    def test_read_and_write_routes_have_validated_public_contracts(self):
        from urllib.parse import urlparse
        read_status, payload = read_catalog.route(urlparse('/api/npc-atlas-sources'),
            {'npc_atlas_sources':self.service},lambda:{})
        self.assertEqual(read_status,200)
        self.assertIn('monster',payload['groups'])
        # Route dependencies are injected, not imported from the host or network.
        with patch('api.write_actors.character_components.write',return_value=None):
            deps={'npc_atlas_sources':self.service,'character_identity':None,
                  'monsters':self.monsters,'npc_equipment':None,'npcs':self.npcs,
                  'publication_credentials':None,'store':None,'sync_character_to_studio':None,
                  'sync_monster_to_studio':None,'sync_weapon_to_studio':None,'weapons':self.weapons,
                  'arrows':None}
            request={'action':'connect','npcSlug':'target','sourceKind':'monster',
                     'sourceSlug':'source','sourceSlot':'atlas','variantId':0,'sourceImageId':'9988776655','expectedRevision':0}
            status, result = write_actors.route('/api/npc-atlas-choice',lambda:request,deps)
            self.assertEqual(status,200)
            self.assertEqual(result['atlas_binding']['published_id'],'9988776655')
            request['sourceKind']='invalid'
            status, result = write_actors.route('/api/npc-atlas-choice',lambda:request,deps)
            self.assertEqual(status,400)
            self.assertIn('category',result['error'])

    def test_atlas_source_picker_never_creates_new_roblox_image(self):
        # An image already uploaded for a Monster can be reused by an NPC.
        with patch('monster_store.create_image_asset',side_effect=AssertionError('cloud upload')):
            with patch('monster_store.update_image_asset',side_effect=AssertionError('cloud update')):
                row = self._select()
                self.assertEqual(row['atlas_binding']['published_id'],'9988776655')
                self.assertTrue(self.atlases.binding('npc','target'))

    def test_stale_image_selection_rejected_before_binding(self):
        with self.assertRaisesRegex(ValueError,'Image ID changed'):
            self.service.connect({'npcSlug':'target','sourceKind':'monster',
                'sourceSlug':'source','sourceSlot':'atlas','variantId':0,'sourceImageId':'123456',
                'expectedRevision':0})
        self.assertIsNone(self.npcs.get('target').get('atlas_binding'))

    def test_shared_atlas_retirement_counts_npc_consumer(self):
        self._select()
        variant_id = self.npcs.get('target')['atlas_binding']['variant_id']
        plan = self.atlases.retirement_plan(variant_id)
        self.assertTrue(any(row['consumer_type']=='npc' and row['consumer_id']=='target'
                            for row in plan['consumers']))
        with self.assertRaisesRegex(ValueError,'in use'):
            self.atlases.retire_variant(variant_id,token=plan['token'])

    def test_ui_defaults_to_npc_and_offers_five_source_categories(self):
        html = (ROOT/'static/index.html').read_text(encoding='utf-8')
        js = (ROOT/'static/npc-assets.js').read_text(encoding='utf-8')
        for key in NpcAtlasSources.GROUPS:
            self.assertIn(f'<option value="{key}">',html)
        self.assertIn("$('npc-atlas-category').value='npc'",js)
        self.assertIn("await request('/api/npc-atlas-sources')",js)
        self.assertIn("await request('/api/npc-atlas-choice'",js)
        self.assertIn('variantId:source.variantId',js)
        self.assertIn('variantId:pending.variantId',js)

    def test_studio_sync_uses_shared_id_and_marks_revision_only_on_success(self):
        self._select()
        calls=[]
        def loader(asset_id,destination,**kwargs):
            calls.append(kwargs['metadata']['textures'])
            return {'monsterStats':{'textures':{'applied':1}}}
        def fail_loader(*args,**kwargs):
            return {'monsterStats':{'textures':{'applied':0}}}
        failed = StudioAssetSyncService(None,None,self.monsters,self.npcs,fail_loader)
        with patch('services.studio_asset_sync.validate_published_rig'):
            with self.assertRaisesRegex(ValueError,'did not apply'):
                failed.sync_monster_to_studio('target',kind='npc')
        self.assertEqual(self.npcs.get('target')['atlas_binding']['syncStatus'],'pending_studio_sync')
        sync = StudioAssetSyncService(None,None,self.monsters,self.npcs,loader)
        with patch('services.studio_asset_sync.validate_published_rig'):
            sync.sync_monster_to_studio('target',kind='npc')
        self.assertEqual([x['assetId'] for x in calls[-1]],['9988776655'])
        self.assertEqual(self.npcs.get('target')['atlas_binding']['syncStatus'],'synced')


if __name__ == '__main__':
    unittest.main()
