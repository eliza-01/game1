"""Location LOD1 contract: optional independent authoring and publication."""
import json
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

CONTROL = Path(__file__).resolve().parents[1] / 'control-center'
sys.path.insert(0, str(CONTROL))
from location_asset_store import LocationAssetStore
from api.write_world import route as write_world
from api.read_world import route as read_world
from urllib.parse import urlparse


class LodAuthoring(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)
        self.store = LocationAssetStore(self.root)
        self.full = self.root / 'full.fbx'
        self.full.write_bytes(b'; FBX 7.4.0\nFBXHeaderExtension: {}\nFULL')
        self.item = self.store.register({'nameEn': 'Test Fence', 'category': 'fence',
            'modelSourcePath': str(self.full), 'appearanceMode': 'material'})
        self.slug = self.item['slug']
        self.lod = self.root / (self.slug + '_lod1.fbx')
        self.lod.write_bytes(b'; FBX 7.4.0\nFBXHeaderExtension: {}\nLOD1')

    def test_missing_is_optional_and_stage_is_idempotent(self):
        self.assertEqual(self.store.get(self.slug)['lod1']['status'], 'NOT_REGISTERED')
        self.assertEqual(self.store.get(self.slug)['status'], 'LOCAL_ONLY')
        previous = self.store.get(self.slug)
        staged = self.store.stage_lod1(self.slug, str(self.lod), 0)
        self.assertEqual(staged['status'], 'STAGED')
        self.assertEqual(self.store.stage_lod1(self.slug, str(self.lod), 1)['revision'], 1)
        self.assertEqual(self.store.get(self.slug)['model_sha256'], previous['model_sha256'])
        self.assertEqual(self.store.get(self.slug)['model_asset_id'], previous['model_asset_id'])
        self.assertEqual(self.store.get(self.slug)['lod1']['revision'], 1)
        self.assertIn('lod1ModelAssetId = ""',
            (self.root/'src/shared/world/LocationAssetRegistry.luau').read_text())
        with self.assertRaisesRegex(ValueError, "changed"):
            self.store.stage_lod1(self.slug, str(self.lod), 0)

    def test_publish_history_restage_rename_retirement(self):
        self.store.stage_lod1(self.slug, str(self.lod), 0)
        @contextmanager
        def fake_staged(root, source, **kwargs):
            self.assertEqual(kwargs['texture_mode'], 'geometry_only')
            yield source
        output = SimpleNamespace(asset_id='34567890', operation_path='operations/lod1', moderation_state='Approved')
        with patch('services.model_lod_common.staged_model', fake_staged), \
             patch('services.model_lod_common.create_model_asset', return_value='operations/lod1') as creator, \
             patch('services.model_lod_common.wait_for_operation', return_value=output):
            published = self.store.publish_lod1(self.slug, 1,
                {'apiKey':'example','creatorId':'123','creatorType':'User'})
            self.assertEqual(published['status'], 'PUBLISHED')
            self.assertEqual(published['modelAssetId'], '34567890')
            self.assertEqual(creator.call_args.kwargs['display_name'], 'test_fence_lod1')
        lua = (self.root / 'src/shared/world/LocationAssetRegistry.luau').read_text()
        self.assertIn('lod1ModelAssetId = "34567890"', lua)
        with patch('services.model_lod_common.create_model_asset') as creator:
            self.assertEqual(self.store.publish_lod1(self.slug, 1, {})['status'], 'PUBLISHED')
            creator.assert_not_called()
        self.lod.write_bytes(b'; FBX 7.4.0\nFBXHeaderExtension: {}\nLOD1 edited')
        staged = self.store.stage_lod1(self.slug, str(self.lod), 1)
        self.assertEqual(staged['status'], 'UPDATE_AVAILABLE')
        self.assertEqual(staged['modelAssetId'], '34567890')
        self.assertIn('lod1ModelAssetId = ""',
            (self.root/'src/shared/world/LocationAssetRegistry.luau').read_text())
        self.assertEqual(len(self.store.lod1_history(self.slug)), 1)
        self.assertEqual(self.store.publications(self.slug)[0]['kind'], 'lod1')
        item = self.store.get(self.slug)
        renamed = self.store.rename_identity(self.slug, {
            'slug':'new_fence', 'nameEn':'Test Fence', 'category':'fence',
            'surfaceMaterial':item['surfaceMaterial'], 'destructible':item['destructible'],
            'appearanceMode':item['appearanceMode'],'visualMaterial':item['visualMaterial'],
            'visualColor':item['visualColor'], 'expectedRevision':item['revision']})
        self.assertEqual(renamed['lod1']['revision'], 2)
        self.assertEqual(self.store.lod1_history('new_fence')[0]['asset_id'], '34567890')
        self.store.delete('new_fence')
        retired = sorted((self.root/'.control-center/location-assets-retired').glob('*.json'))
        self.assertTrue(retired)
        self.assertEqual(json.loads(retired[-1].read_text())['lodResources'][0]['asset_id'], '34567890')

    def test_reject_invalid_and_stale_requests_without_touching_full(self):
        wrong = self.root / 'lod.fbx'
        wrong.write_bytes(self.lod.read_bytes())
        with self.assertRaisesRegex(ValueError, self.slug + '_lod1.fbx'):
            self.store.stage_lod1(self.slug, str(wrong), 0)
        with self.assertRaisesRegex(ValueError, 'FBX'):
            self.store.stage_lod1(self.slug, str(self.root/'none.fbx'), 0)
        with self.assertRaisesRegex(ValueError, "changed"):
            self.store.stage_lod1(self.slug, str(self.lod), 4)
        self.store.stage_lod1(self.slug, str(self.lod), 0)
        with self.assertRaisesRegex(ValueError, "changed"):
            self.store.publish_lod1(self.slug, 42, {})
        # Existing FULL geometry and appearance never enter the LOD publication.
        self.assertIsNone(self.store.get(self.slug)['model_asset_id'])
        self.assertEqual(self.store.get(self.slug)['appearanceMode'], 'material')

    def test_http_routes_and_kanban_digest(self):
        def body():return {'sourcePath': str(self.lod),'expectedRevision':0}
        # This endpoint is within write_world; dependencies supplied normally by composition root.
        deps={'location_assets':self.store, 'deco_layouts':None, 'locations':None,
              'monster_spawns':None,'npc_place_spawn':None,'npc_register_spawn':None,
              'npc_spawns':None,'options_store':None,'publication_credentials':lambda _: {},
              'request_active_studio_save':None,'run_timeline_editor_bridge':None,
              'sync_monster_to_studio':None,'timelines':None}
        status,response=write_world('/api/location-assets/'+self.slug+'/lod1-stage',body,deps)
        self.assertEqual(status,200,response)
        self.assertEqual(response['revision'],1)
        status,response=read_world(urlparse('/api/location-assets/'+self.slug+'/lod1-history'),
                                   {'location_assets':self.store},lambda: {})
        self.assertEqual((status,response['items']), (200,[]))
        status,_=write_world('/api/location-assets/'+self.slug+'/lod1-stage',
                             lambda:{'sourcePath':str(self.lod),'expectedRevision':0},deps)
        self.assertEqual(status,400)
        from kanban_store import KanbanStore
        card=KanbanStore(Path(__file__).resolve().parents[2]).detail('KBN-0016')
        self.assertEqual(card['card']['id'], 'KBN-0016')


if __name__ == '__main__':
    unittest.main()
