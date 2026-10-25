"""Atlas republish: new ID on changed bytes, atomic consumer updates, no reimport."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase, mock
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from location_asset_store import LocationAssetStore
from api.write_world import route


class AtlasRepublishM129(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'incoming'
        self.source.mkdir()
        self.image = self.source / 'wooden_post_kit_64x64_atlas.png'
        Image.new('RGB', (64, 64), 'red').save(self.image)
        self.fbx = self.source / 'post.fbx'
        self.fbx.write_bytes(b'FBX test')
        self.loc = LocationAssetStore(self.root)
        self.atlases = self.loc.atlases
        self.first = self.loc.register({'slug':'wooden_post_01', 'nameEn':'Post 01', 'category':'decoration',
                                        'modelSourcePath':str(self.fbx), 'textureSourcePath':str(self.image)})
        self.vid = self.first['atlasVariantId']
        self.creds = {'apiKey':'fake', 'creatorType':'User','creatorId':'1'}

    def publish_as(self, image_id):
        with mock.patch('services.texture_atlas_registry.create_image_asset',return_value='operations/test') as upload, \
             mock.patch('services.texture_atlas_registry.wait_for_operation',return_value=SimpleNamespace(
                 asset_id=str(image_id),operation_path='operations/test',moderation_state='Approved')):
            result = self.atlases.ensure_published(self.vid,self.creds,'test')
        return result, upload

    def test_republish_updates_all_consumers_and_archives_previous_id(self):
        old, old_upload = self.publish_as(111)
        self.assertEqual(old_upload.call_count,1)
        self.loc.register({'slug':'wooden_post_02','nameEn':'Post 02','category':'decoration',
                           'modelSourcePath':str(self.fbx),'atlasVariantId':self.vid})
        self.atlases.bind('real_estate','house_level2_01:house',self.vid)
        for consumer, name in [('location_asset','wooden_post_01'), ('location_asset','wooden_post_02'),
                               ('real_estate','house_level2_01:house')]:
            self.atlases.mark_synced(consumer,name,1)
        old_path = self.root / old['source_path']
        old_sha = old['source_sha256']
        Image.new('RGB',(64,64),'green').save(self.image)
        staged = self.atlases.register_file(str(self.image))
        self.assertEqual(staged['id'],self.vid)
        self.assertTrue(staged['replacementPending'])
        self.assertTrue(staged['current'])
        self.assertEqual(self.loc.get('wooden_post_02')['texture_asset_id'],'111')
        self.assertEqual(self.atlases.binding('real_estate','house_level2_01:house')['published_id'],'111')
        latest, upload = self.publish_as(222)
        self.assertEqual(upload.call_count,1)
        self.assertNotEqual(latest['source_sha256'],old_sha)
        self.assertEqual(latest['published_id'],'222')
        self.assertFalse(latest['replacementPending'])
        self.assertTrue(latest['current'])
        self.assertTrue(old_path.is_file())
        self.assertEqual(self.loc.get('wooden_post_01')['texture_asset_id'],'222')
        self.assertEqual(self.loc.get('wooden_post_02')['texture_asset_id'],'222')
        self.assertEqual(self.atlases.binding('real_estate','house_level2_01:house')['published_id'],'222')
        for entry in self.atlases.consumers(self.vid):
            self.assertEqual(entry['revision'],2)
            self.assertEqual(self.atlases.binding(entry['consumer_type'],entry['consumer_id'])['syncStatus'], 'pending_studio_sync')
        with self.atlases.connect() as db:
            pubs = db.execute('SELECT image_asset_id,sha256 FROM texture_atlas_publications WHERE variant_id=? ORDER BY id',(self.vid,)).fetchall()
        self.assertEqual([x[0] for x in pubs],['111','222'])
        self.assertEqual(pubs[0][1],old_sha)
        with mock.patch('services.texture_atlas_registry.create_image_asset') as duplicate:
            self.atlases.register_file(str(self.image))
            same = self.atlases.ensure_published(self.vid,{},'same')
            duplicate.assert_not_called()
        self.assertEqual(same['published_id'],'222')

    def test_upload_failure_keeps_current_id_and_prohibits_ambiguous_retry(self):
        self.publish_as(111)
        Image.new('RGB',(64,64),'green').save(self.image)
        self.atlases.register_file(str(self.image))
        with mock.patch('services.texture_atlas_registry.create_image_asset',side_effect=TimeoutError('ambiguous')) as upload:
            with self.assertRaises(TimeoutError):
                self.atlases.ensure_published(self.vid,self.creds,'test')
            with self.assertRaisesRegex(ValueError,'unresolved'):
                self.atlases.ensure_published(self.vid,self.creds,'test')
            upload.assert_called_once()
        self.assertEqual(self.loc.get('wooden_post_01')['texture_asset_id'],'111')
        self.assertTrue(self.atlases.get_variant(self.vid)['replacementPending'])
        with self.assertRaisesRegex(ValueError,'unresolved'):
            self.atlases.register_file(str(self.image))

    def test_wrong_name_or_dimensions_cannot_overwrite(self):
        self.publish_as(111)
        wrong = self.source/'other_64x64_atlas.png'
        Image.new('RGB',(64,64),'blue').save(wrong)
        new = self.atlases.register_file(str(wrong))
        self.assertNotEqual(new['id'],self.vid)
        invalid = self.source/'wooden_post_kit_64x64_atlas.png'
        Image.new('RGB',(32,32),'blue').save(invalid)
        with self.assertRaisesRegex(ValueError, 'but image is'):
            self.atlases.register_file(str(invalid))
        self.assertFalse(self.atlases.get_variant(self.vid)['replacementPending'])

    def test_republish_route_sync_errors_leave_new_published_id_and_pending_revision(self):
        self.publish_as(111)
        Image.new('RGB',(64,64),'blue').save(self.image)
        deps = dict.fromkeys(('deco_layouts','locations','monster_spawns','npc_place_spawn',
            'npc_register_spawn','npc_spawns','options_store','request_active_studio_save',
            'run_timeline_editor_bridge','sync_monster_to_studio','timelines'))
        deps.update(location_assets=self.loc, real_estate=SimpleNamespace(export=mock.Mock()),
                    publication_credentials=lambda description: self.creds,
                    sync_location_assets_to_studio=mock.Mock(side_effect=RuntimeError('Studio offline')),
                    sync_real_estate_to_studio=mock.Mock())
        with mock.patch('services.texture_atlas_registry.create_image_asset',return_value='operations/2'),\
             mock.patch('services.texture_atlas_registry.wait_for_operation',return_value=SimpleNamespace(
                 asset_id='222',operation_path='operations/2',moderation_state='Approved')):
            status, payload = route(f'/api/texture-atlases/variants/{self.vid}/republish',
                            lambda:{'sourcePath':str(self.image)}, deps)
        self.assertEqual(status,200,payload)
        self.assertEqual(payload['variant']['published_id'],'222')
        self.assertEqual(payload['syncedConsumers'],0)
        self.assertEqual(payload['pendingConsumers'],1)
        self.assertIn('Studio offline',payload['studioErrors'][0])
        self.assertEqual(self.loc.get('wooden_post_01')['texture_asset_id'],'222')
        self.assertEqual(self.atlases.binding('location_asset','wooden_post_01')['syncStatus'],'pending_studio_sync')
        self.assertTrue(deps['real_estate'].export.called)

    def test_republish_route_reuses_same_bytes_without_new_asset(self):
        self.publish_as(111)
        deps = dict.fromkeys(('deco_layouts','locations','monster_spawns','npc_place_spawn',
            'npc_register_spawn','npc_spawns','options_store','request_active_studio_save',
            'run_timeline_editor_bridge','sync_monster_to_studio','timelines'))
        deps.update(location_assets=self.loc, real_estate=SimpleNamespace(export=mock.Mock()),
                    publication_credentials=lambda description: self.creds,
                    sync_location_assets_to_studio=mock.Mock(),sync_real_estate_to_studio=mock.Mock())
        with mock.patch('services.texture_atlas_registry.create_image_asset') as upload:
            status, payload = route(f'/api/texture-atlases/variants/{self.vid}/republish',
                                    lambda:{'sourcePath':str(self.image)},deps)
        self.assertEqual(status,200,payload)
        self.assertTrue(payload['unchanged'])
        upload.assert_not_called()
        deps['sync_location_assets_to_studio'].assert_not_called()

    def test_republish_route_syncs_all_consumers_using_exact_variant(self):
        self.publish_as(111)
        self.loc.register({'slug':'wooden_post_02','nameEn':'Post 02','category':'decoration',
                           'modelSourcePath':str(self.fbx),'atlasVariantId':self.vid})
        self.atlases.bind('real_estate','house_level2_01:house',self.vid)
        Image.new('RGB',(64,64),'green').save(self.image)
        deps = dict.fromkeys(('deco_layouts','locations','monster_spawns','npc_place_spawn',
            'npc_register_spawn','npc_spawns','options_store','request_active_studio_save',
            'run_timeline_editor_bridge','sync_monster_to_studio','timelines'))
        def ack_real_estate(slug):
            self.assertEqual(slug, 'house_level2_01')
            self.atlases.mark_synced('real_estate', f'{slug}:house', 2)
            return {'studio':{'texturesApplied': 1}}
        deps.update(location_assets=self.loc, real_estate=SimpleNamespace(export=mock.Mock()),
                    publication_credentials=lambda description: self.creds,
                    sync_location_assets_to_studio=mock.Mock(return_value={'models':2}),
                    sync_real_estate_to_studio=mock.Mock(side_effect=ack_real_estate))
        with mock.patch('services.texture_atlas_registry.create_image_asset',return_value='operations/new'),\
             mock.patch('services.texture_atlas_registry.wait_for_operation',return_value=SimpleNamespace(
                 asset_id='222',operation_path='operations/new',moderation_state='Approved')):
            status, payload = route(f'/api/texture-atlases/variants/{self.vid}/republish',
                                    lambda:{'sourcePath':str(self.image)},deps)
        self.assertEqual(status,200,payload)
        self.assertEqual(payload['syncedConsumers'],3)
        self.assertEqual(payload['pendingConsumers'],0)
        self.assertEqual(payload['studioErrors'],[])
        deps['sync_location_assets_to_studio'].assert_called_once_with()
        deps['sync_real_estate_to_studio'].assert_called_once_with('house_level2_01')
        for item in self.atlases.consumers(self.vid):
            self.assertEqual(self.atlases.binding(item['consumer_type'],item['consumer_id'])['syncStatus'],'synced')

    def test_wrong_republish_filename_rejected_before_staging(self):
        self.publish_as(111)
        filename = self.source/'different_family_64x64_atlas.png'
        Image.new('RGB',(64,64),'green').save(filename)
        deps = dict.fromkeys(('deco_layouts','locations','monster_spawns','npc_place_spawn',
            'npc_register_spawn','npc_spawns','options_store','request_active_studio_save',
            'run_timeline_editor_bridge','sync_monster_to_studio','timelines'))
        deps.update(location_assets=self.loc, real_estate=SimpleNamespace(export=mock.Mock()),
                    publication_credentials=lambda description:self.creds,
                    sync_location_assets_to_studio=mock.Mock(), sync_real_estate_to_studio=mock.Mock())
        with mock.patch('services.texture_atlas_registry.create_image_asset') as upload:
            status,payload=route(f'/api/texture-atlases/variants/{self.vid}/republish',
                                  lambda:{'sourcePath':str(filename)},deps)
        self.assertEqual(status,400,payload)
        self.assertIn('must match this atlas',payload['error'])
        self.assertFalse(self.atlases.get_variant(self.vid)['replacementPending'])
        self.assertEqual(len(self.atlases.catalog()),1)
        upload.assert_not_called()
