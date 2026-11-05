"""M233: model-only means no atlas upload and no embedded image bytes.

No Roblox/Open Cloud access is needed. Fake Blender proves the staging
contract and the server rejects any staging report without a texture-free proof.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from model_publication_service import staged_model
from location_asset_store import LocationAssetStore
from api.write_world import route
from PIL import Image


class ModelOnlyM233(unittest.TestCase):
    def test_geometry_only_staging_requires_verifiable_texture_free_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'sample.fbx'
            source.write_bytes(b'artist data remains intact')
            calls = []

            def prepare(command, **kwargs):
                calls.append(command)
                self.assertEqual(command[-1], 'geometry_only')
                output, report = map(Path, command[-3:-1])
                output.write_bytes(b'prepared geometry only')
                report.write_text(json.dumps({'schemaVersion': 1, 'restTransformsChanged': False,
                                              'textureMode': 'geometry_only', 'materialSlots': 0}))
                return SimpleNamespace(returncode=0)

            with mock.patch('model_publication_service.blender_executable', return_value=Path('blender')), \
                    mock.patch('model_publication_service.subprocess.run', side_effect=prepare):
                with staged_model(root, source, texture_mode='geometry_only') as path:
                    self.assertEqual(path.read_bytes(), b'prepared geometry only')
                self.assertFalse(path.exists())
            self.assertEqual(source.read_bytes(), b'artist data remains intact')
            self.assertEqual(len(calls), 1)

    def test_bad_texture_report_refuses_upload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'sample.fbx'
            source.write_bytes(b'artist data')

            def prepare(command, **kwargs):
                Path(command[-3]).write_bytes(b'fbx')
                Path(command[-2]).write_text(json.dumps({'schemaVersion': 1,
                    'restTransformsChanged': False, 'textureMode': 'embedded', 'materialSlots': 1}))
                return SimpleNamespace(returncode=0)

            with mock.patch('model_publication_service.blender_executable', return_value=Path('blender')), \
                    mock.patch('model_publication_service.subprocess.run', side_effect=prepare):
                with self.assertRaisesRegex(ValueError, 'texture-free FBX'):
                    with staged_model(root, source, texture_mode='geometry_only'):
                        self.fail('unsafe model upload')

    def test_location_model_republish_does_not_publish_atlas_or_change_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'campfire.fbx'; source.write_bytes(b'fake source FBX')
            atlas = root / 'campfire_64x64_atlas.png'
            Image.new('RGBA', (64, 64), (1, 2, 3, 255)).save(atlas)
            store = LocationAssetStore(root)
            row = store.register({'slug': 'campfire_01', 'nameEn': 'Campfire',
                'category': 'prop', 'modelSourcePath': str(source),
                'textureSourcePath': str(atlas), 'createOnly': True})
            with store.connect() as connection:
                connection.execute('UPDATE texture_atlas_variants SET published_id=?, '
                    'published_sha256=source_sha256 WHERE id=?', ('700123', row['atlasVariantId']))

            @contextmanager
            def stage(_, model, *, texture_mode='embedded'):
                self.assertEqual(texture_mode, 'geometry_only')
                yield model

            with mock.patch('location_asset_store.staged_model', side_effect=stage), \
                    mock.patch('location_asset_store.create_model_asset', return_value='operations/model'), \
                    mock.patch('location_asset_store.wait_for_operation', return_value=SimpleNamespace(
                        asset_id='800123', operation_path='operations/model', moderation_state='Approved')), \
                    mock.patch('services.texture_atlas_registry.create_image_asset',
                               side_effect=AssertionError('unexpected Image upload')):
                new = store.publish('campfire_01', {'apiKey': 'unused',
                    'creatorType': 'user', 'creatorId': '1'}, scope='model', force_model=True)
            self.assertEqual(new['model_asset_id'], '800123')
            self.assertEqual(new['texture_asset_id'], '700123')
            self.assertEqual(new['atlasVariantId'], row['atlasVariantId'])

    def test_new_api_route_enforces_model_only(self):
        asset = mock.Mock()
        asset.get.return_value = {'model_asset_id': '111', 'texture_asset_id': '222'}
        asset.publish.return_value = {'model_asset_id': '333', 'texture_asset_id': '222'}
        requirements = ('deco_layouts','locations','monster_spawns','npc_place_spawn',
            'npc_register_spawn','npc_spawns','options_store','request_active_studio_save',
            'run_timeline_editor_bridge','sync_monster_to_studio','timelines')
        deps = {name: mock.Mock() for name in requirements}
        deps['location_assets'] = asset
        deps['publication_credentials'] = lambda description: {'description': description}
        path = '/api/location-assets/campfire_01/publish-model'
        status, result = route(path, lambda: {'forceModel': True}, deps)
        self.assertEqual(status, 200)
        self.assertEqual(result['resourceKind'], 'Model')
        self.assertTrue(result['atlasUnchanged'])
        self.assertEqual(result['model_asset_id'], '333')
        asset.publish.assert_called_once()
        self.assertEqual(asset.publish.call_args.kwargs,
                         {'scope': 'model', 'force_model': True})
        asset.reset_mock()
        status, result = route(path, lambda: {'scope': 'changed'}, deps)
        self.assertEqual(status, 400)
        asset.publish.assert_not_called()

    def test_model_stage_script_never_uses_embed_mode_for_location(self):
        source = (ROOT / 'system/asset-manager/prepare_model_publication_fbx.py').read_text()
        self.assertIn('obj.data.materials.clear()', source)
        self.assertIn('no_textures=(texture_mode == "geometry_only")', source)
        workflow = (ROOT / 'system/control-center/static/deco-assets.js').read_text()
        self.assertIn('`/api/location-assets/${encodeURIComponent(slug)}/publish-model`', workflow)
        self.assertIn('scope !== \'model\'', workflow)
        # The weapon pipeline continues to use the shared embedded-staging mode.
        weapon = (ROOT / 'system/control-center/weapon_store.py').read_text()
        self.assertIn('with staged_model(self.root, model) as publication:', weapon)


if __name__ == '__main__':
    unittest.main()
