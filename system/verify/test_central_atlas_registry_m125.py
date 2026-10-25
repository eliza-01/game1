"""Central atlas invariants and backwards-compatible Location Asset adapter."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase, mock
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from location_asset_store import LocationAssetStore
from services.texture_atlas_registry import parse_filename


class CentralAtlasM125(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'incoming'
        self.source.mkdir()
        self.image = self.source / 'wooden_post_kit_128x256_atlas.png'
        Image.new('RGBA', (128, 256), (12, 40, 80, 100)).save(self.image)
        self.fbx = self.source / 'wooden_post.fbx'
        self.fbx.write_bytes(b'FBX version')
        self.location = LocationAssetStore(self.root)

    def register(self, slug, variant_id=None):
        payload = {'nameEn': slug.replace('_',' ').title(), 'slug': slug, 'category': 'decoration',
                   'modelSourcePath': str(self.fbx)}
        if variant_id:
            payload['atlasVariantId'] = variant_id
        else:
            payload['textureSourcePath'] = str(self.image)
        return self.location.register(payload)

    def fake_publication(self):
        return SimpleNamespace(asset_id='7654321', operation_path='fake-operation', moderation_state='Approved')

    def test_filename_dimensions_are_independent_of_model_name(self):
        self.assertEqual(parse_filename('wooden_post_kit_128x1024_atlas.png')['width'], 128)
        self.assertEqual(parse_filename('wooden_post_kit_128x1024_atlas.png')['height'], 1024)
        self.assertEqual(parse_filename('wooden_post_kit_atlas.png'), None)
        self.assertEqual(parse_filename('../evil_32x32_atlas.png'), None)
        self.assertEqual(parse_filename('wooden_post_kit_128x1024_atlas.png.exe'), None)

    def test_registration_is_idempotent_and_conflict_safe(self):
        first = self.location.atlases.register_file(str(self.image))
        same = self.location.atlases.register_file(str(self.image))
        self.assertEqual(first['id'], same['id'])
        self.assertEqual(len(self.location.atlases.catalog()),1)
        Image.new('RGB', (128, 256), 'red').save(self.image)
        staged = self.location.atlases.register_file(str(self.image))
        self.assertEqual(first['id'], staged['id'])
        self.assertTrue(staged['replacementPending'])
        # The active variant remains unchanged until publication succeeds.
        saved = self.root / first['source_path']
        self.assertTrue(saved.is_file())
        self.assertEqual(self.location.atlases.get_variant(first['id'])['source_sha256'], first['source_sha256'])

    def test_wrong_actual_resolution_never_registers(self):
        wrong = self.source / 'misleading_512x512_atlas.png'
        Image.new('RGB', (64, 64)).save(wrong)
        with self.assertRaisesRegex(ValueError, 'but image is 64x64'):
            self.location.atlases.register_file(str(wrong))
        self.assertEqual(self.location.atlases.catalog(), [])

    def test_one_image_id_two_models_and_independent_binding(self):
        first = self.register('wooden_post_01')
        variant_id = first['atlasVariantId']
        self.assertEqual(first['status'], 'LOCAL_ONLY')
        with mock.patch('services.texture_atlas_registry.create_image_asset') as upload, \
             mock.patch('services.texture_atlas_registry.wait_for_operation', return_value=self.fake_publication()):
            self.location.atlases.ensure_published(variant_id, {'apiKey':'fake','creatorType':'User','creatorId':'1'}, 'demo')
            self.location.atlases.ensure_published(variant_id, {'apiKey':'fake','creatorType':'User','creatorId':'1'}, 'demo')
        self.assertEqual(upload.call_count, 1)
        second = self.register('wooden_bridge_bar_01',variant_id)
        self.assertEqual(self.location.get('wooden_post_01')['texture_asset_id'], '7654321')
        self.assertEqual(second['texture_asset_id'], '7654321')
        self.assertEqual(self.location.get('wooden_bridge_bar_01')['atlasFamily'], 'wooden_post_kit')
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.location.select_atlas('wooden_bridge_bar_01', variant_id, expected_revision=8)
        # Same variant is a no-op; no double upload, no revision jump.
        self.assertEqual(self.location.select_atlas('wooden_bridge_bar_01',variant_id,1)['bindingRevision'],1)
        self.assertEqual(self.location.atlases.binding('location_asset','wooden_post_01')['syncStatus'],'pending_studio_sync')
        self.assertTrue(self.location.atlases.mark_synced('location_asset','wooden_post_01',1))
        self.assertFalse(self.location.atlases.mark_synced('location_asset','wooden_post_01',0))
        self.assertEqual(self.location.atlases.binding('location_asset','wooden_post_01')['syncStatus'],'synced')

    def test_different_resolution_keeps_separate_selection(self):
        first = self.register('wooden_post_01')
        second_img = self.source / 'wooden_post_kit_64x128_atlas.png'
        Image.new('RGB',(64,128),'blue').save(second_img)
        smaller = self.location.atlases.register_file(str(second_img))
        with self.location.connect() as db:
            db.execute('''UPDATE texture_atlas_variants SET published_id=?,published_sha256=source_sha256 WHERE id=?''',
                       ('42', smaller['id']))
        other = self.register('wooden_bridge_bar_01',smaller['id'])
        self.assertEqual(other['texture_asset_id'],'42')
        self.assertNotEqual(first['atlasVariantId'],other['atlasVariantId'])
        family = self.location.atlases.catalog()[0]
        self.assertEqual([v['resolution'] for v in family['variants']],['128x256','64x128'])

    def test_legacy_duplicate_ids_are_not_arbitrarily_canonicalized(self):
        first = self.register('wooden_post_01')
        second = self.register('wooden_bridge_bar_01',first['atlasVariantId'])
        sha = first['texture_sha256']
        with self.location.connect() as db:
            db.execute('UPDATE location_assets SET texture_reference_slug="",texture_asset_id=?,texture_sha256=?,texture_published_sha256=? WHERE slug=?', ('111',sha,sha,'wooden_post_01'))
            db.execute('UPDATE location_assets SET texture_reference_slug="",texture_asset_id=?,texture_sha256=?,texture_published_sha256=? WHERE slug=?', ('222',sha,sha,'wooden_bridge_bar_01'))
        self.location._index_legacy_texture_publications()
        with mock.patch('services.texture_atlas_registry.create_image_asset') as upload:
            with self.assertRaisesRegex(ValueError,'legacy atlas publication conflict'):
                self.location.atlases.ensure_published(first['atlasVariantId'],{},'demo')
            upload.assert_not_called()
        self.assertIsNone(self.location.atlases.get_variant(first['atlasVariantId'])['published_id'])

    def test_legacy_unique_id_reuses_exact_bytes_without_upload(self):
        row = self.register('wooden_post_01')
        sha = row['texture_sha256']
        with self.location.connect() as db:
            db.execute('UPDATE location_assets SET texture_asset_id=?,texture_published_sha256=? WHERE slug=?', ('111',sha,'wooden_post_01'))
        self.location._index_legacy_texture_publications()
        with mock.patch('services.texture_atlas_registry.create_image_asset') as upload:
            published = self.location.atlases.ensure_published(row['atlasVariantId'], {}, 'demo')
            upload.assert_not_called()
        self.assertEqual(published['published_id'],'111')

    def test_model_publish_with_published_variant_does_not_upload_image(self):
        row = self.register('wooden_post_01')
        variant_id = row['atlasVariantId']
        with self.location.connect() as db:
            db.execute('UPDATE location_assets SET model_asset_id=?,model_published_sha256=model_sha256 WHERE slug=?',
                       ('31415','wooden_post_01'))
            db.execute('UPDATE texture_atlas_variants SET published_id=?,published_sha256=source_sha256 WHERE id=?',
                       ('7654321',variant_id))
        with mock.patch('location_asset_store.create_image_asset') as legacy_upload, \
             mock.patch('location_asset_store.create_model_asset') as model_upload, \
             mock.patch('services.texture_atlas_registry.create_image_asset') as atlas_upload:
            published = self.location.publish('wooden_post_01', {})
        legacy_upload.assert_not_called()
        model_upload.assert_not_called()
        atlas_upload.assert_not_called()
        self.assertEqual(published['texture_asset_id'],'7654321')

    def test_switch_does_not_rebind_other_model_or_accept_stale_ack(self):
        first = self.register('wooden_post_01')
        second = self.register('wooden_bridge_bar_01',first['atlasVariantId'])
        small = self.source / 'wooden_post_kit_64x64_atlas.png'
        Image.new('RGB',(64,64),'green').save(small)
        small_var = self.location.atlases.register_file(str(small))
        with self.location.connect() as db:
            db.execute('UPDATE texture_atlas_variants SET published_id=?,published_sha256=source_sha256 WHERE id=?',
                       ('199',small_var['id']))
        changed = self.location.select_atlas('wooden_post_01', small_var['id'], expected_revision=1)
        self.assertEqual(changed['bindingRevision'],2)
        self.assertEqual(changed['texture_asset_id'],'199')
        self.assertEqual(self.location.get('wooden_bridge_bar_01')['atlasVariantId'],second['atlasVariantId'])
        self.assertEqual(self.location.atlases.mark_synced('location_asset','wooden_post_01',1),False)
        self.assertEqual(self.location.atlases.binding('location_asset','wooden_post_01')['syncStatus'],'pending_studio_sync')
        self.assertTrue(self.location.atlases.mark_synced('location_asset','wooden_post_01',2))
        self.assertEqual(self.location.atlases.binding('location_asset','wooden_post_01')['syncStatus'],'synced')

    def test_ambiguous_open_cloud_result_never_reuploads_automatically(self):
        row = self.register('wooden_post_01')
        variant_id = row['atlasVariantId']
        credentials = {'apiKey':'fake','creatorType':'User','creatorId':'1'}
        with mock.patch('services.texture_atlas_registry.create_image_asset',
                        side_effect=TimeoutError('request may already have been accepted')) as upload:
            with self.assertRaises(TimeoutError):
                self.location.atlases.ensure_published(variant_id, credentials, 'demo')
            with self.assertRaisesRegex(ValueError,'unresolved'):
                self.location.atlases.ensure_published(variant_id, credentials, 'demo')
        self.assertEqual(upload.call_count, 1)
        with self.location.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM texture_atlas_pending_uploads').fetchone()[0],1)

    def test_legacy_source_name_has_warning_and_no_destructive_migration(self):
        legacy = self.source / 'old texture.png'
        legacy.write_bytes(b'legacy fixture')
        self.location.register({'slug':'stone_lamp','nameEn':'Stone Lamp','category':'light',
                                'modelSourcePath':str(self.fbx),'textureSourcePath':str(legacy)})
        result = self.location.get('stone_lamp')
        self.assertTrue(result['atlasLegacyWarning'])
        self.assertEqual(result['texture_filename'],'old texture.png')
        self.assertFalse(result.get('atlasVariantId'))
        self.assertTrue((self.root / result['texture_path']).is_file())

class ScopedAtlasBridgeM125(TestCase):
    def test_targeted_sync_requires_matching_revision_ack(self):
        import json
        import socket
        import threading
        import time
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError, URLError
        from services import studio_deco_bridge as bridge

        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0))
            port = sock.getsockname()[1]
        outcome = {}
        def worker():
            try:
                outcome['value'] = bridge.run_deco_refresh_bridge(
                    slug='wooden_post_01', binding_revision=3, timeout_seconds=5)
            except Exception as error:
                outcome['error'] = error
        with mock.patch.object(bridge, 'PORT', port):
            thread = threading.Thread(target=worker, daemon=True)
            thread.start()
            def call(path, data=None):
                payload = json.dumps(data).encode() if data is not None else None
                method = 'POST' if data is not None else 'GET'
                request = Request(f'http://127.0.0.1:{port}{path}', data=payload,
                    method=method, headers={'X-Game1-Token':bridge.TOKEN,
                                              'Content-Type':'application/json'})
                with urlopen(request,timeout=2) as response:
                    return json.load(response)
            command = None
            for _ in range(100):
                try:
                    command = call('/command')
                    break
                except (URLError, OSError):
                    time.sleep(.02)
            self.assertIsNotNone(command)
            self.assertEqual(command['schemaVersion'],2)
            self.assertEqual(command['targetSlug'],'wooden_post_01')
            self.assertEqual(command['bindingRevision'],3)
            with self.assertRaises(HTTPError) as mismatch:
                call('/deco-refresh-result', {**command, 'bindingRevision':2,
                     'models':1,'parts':2,'registryItems':5})
            self.assertEqual(mismatch.exception.code,400)
            call('/deco-refresh-result', {**command, 'matchedModels':4,
                  'models':1,'parts':2,'registryItems':5})
            thread.join(6)
            self.assertFalse(thread.is_alive())
            self.assertNotIn('error',outcome)
            self.assertEqual(outcome['value']['matchedModels'],4)
            self.assertEqual(outcome['value']['bindingRevision'],3)
