"""M107: independent create-only publication of Real Estate Model/Images."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from real_estate.store import RealEstateStore
from api import real_estate
from test_real_estate_m107 import skeleton


class IndependentAssetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        folder = self.root / 'incoming'
        folder.mkdir()
        self.fbx = folder / 'house_level1_01.fbx'
        self.fbx.write_bytes(b'first FBX')
        self.house = folder / 'house.webp'
        self.house.write_bytes(b'first house texture')
        self.door = folder / 'door.webp'
        self.door.write_bytes(b'first door texture')
        self.credentials = {'apiKey':'test', 'creatorType':'user', 'creatorId':'123'}
        self.payload = {'houseType':'house', 'level':1, 'variant':'01',
                        'sourcePath':str(self.fbx),
                        'textures':{'house':str(self.house), 'door':str(self.door)}}
        self.store = RealEstateStore(self.root)
        with patch('real_estate.store.inspect', return_value=skeleton()):
            self.initial = self.store.register(self.payload)
        self.uploads = []
        self.asset_counter = 80000

    def prepared_model(self, root, source, target, skeleton_data, textures):
        self.assertEqual(set(textures), {'house', 'door'})
        self.assertEqual(len(skeleton_data['meshes']), 2)
        target.mkdir(parents=True, exist_ok=True)
        for part in ('house', 'door'):
            (target / (part + '.fbx')).write_bytes(b'prepared rig preserving FBX')
        self.uploads.append('prepare_model')

    def prepared_image(self, root, part, source, staging):
        target = staging / (part + '.png')
        target.write_bytes(b'prepared texture')
        return target

    def upload_model(self, path, **kwargs):
        self.assertTrue(path.is_file())
        self.uploads.append('model:'+path.stem)
        return 'operations/model'

    def upload_image(self, path, **kwargs):
        self.assertTrue(path.is_file())
        self.uploads.append(kwargs['display_name'].split()[-1])
        return 'operations/' + kwargs['display_name'].split()[-1]

    def await_operation(self, op, **kwargs):
        self.asset_counter += 1
        return SimpleNamespace(asset_id=str(self.asset_counter), operation_path=op,
                               moderation_state='Approved')

    def publish(self, scope='all'):
        with patch('real_estate.store.prepare_publication', side_effect=self.prepared_model), \
             patch('real_estate.store.prepare_texture', side_effect=self.prepared_image), \
             patch('real_estate.store.create_model_asset', side_effect=self.upload_model), \
             patch('real_estate.store.create_image_asset', side_effect=self.upload_image), \
             patch('real_estate.store.wait_for_operation', side_effect=self.await_operation):
            return self.store.publish('house_level1_01', self.credentials, scope=scope)

    def start_published(self):
        row = self.publish()
        self.assertEqual(self.uploads, ['prepare_model','model:house','model:door','house','door'])
        self.assertEqual(row['status'], 'PUBLISHED')
        self.uploads.clear()
        return row

    def edit(self, *, new_fbx=None, new_house=None, new_door=None):
        old = self.store.get('house_level1_01')
        textures = {part: value['path'] for part, value in old['textures'].items()}
        if new_house:
            textures['house'] = str(new_house)
        if new_door:
            textures['door'] = str(new_door)
        data = {**self.payload, 'existingSlug':old['slug'],
                'sourcePath':str(new_fbx) if new_fbx else '', 'textures':textures}
        with patch('real_estate.store.inspect', return_value=skeleton()):
            return self.store.register(data)

    def test_house_replacement_creates_only_new_house_image_id(self):
        original = self.start_published()
        source = self.root / 'new-house.png'
        source.write_bytes(b'another house image')
        pending = self.edit(new_house=source)
        self.assertEqual(pending['textures']['house']['assetId'], original['textures']['house']['assetId'])
        self.assertEqual(pending['model_asset_id'], original['model_asset_id'])
        self.assertEqual(pending['publicationCurrent'], {'model':True,'house':False,'door':True})
        changed = self.publish('house')
        self.assertEqual(self.uploads, ['house'])
        self.assertNotEqual(changed['textures']['house']['assetId'], original['textures']['house']['assetId'])
        self.assertEqual(changed['textures']['door']['assetId'], original['textures']['door']['assetId'])
        self.assertEqual(changed['model_asset_id'], original['model_asset_id'])
        self.assertEqual(changed['status'], 'PUBLISHED')
        self.assertEqual(len(self.store.publications(changed['slug'])), 5)
        self.uploads.clear()
        self.publish('all')
        self.assertEqual(self.uploads, [])

    def test_fbx_replacement_creates_only_new_model_asset_id(self):
        original = self.start_published()
        next_fbx = self.root / 'revised.fbx'
        next_fbx.write_bytes(b'second FBX (two same armatures)')
        pending = self.edit(new_fbx=next_fbx)
        self.assertEqual(pending['publicationCurrent'], {'model':False,'house':True,'door':True})
        self.assertEqual(pending['model_asset_id'], original['model_asset_id'])
        changed = self.publish('model')
        self.assertEqual(self.uploads, ['prepare_model','model:house','model:door'])
        self.assertNotEqual(changed['model_asset_id'], original['model_asset_id'])
        for part in ('house','door'):
            self.assertEqual(changed['textures'][part]['assetId'], original['textures'][part]['assetId'])
        self.assertEqual(changed['status'], 'PUBLISHED')

    def test_texture_publication_does_not_touch_pending_fbx(self):
        original = self.start_published()
        next_fbx = self.root/'new.fbx'; next_fbx.write_bytes(b'FBX 3')
        next_door = self.root/'door.jpeg'; next_door.write_bytes(b'door 3')
        self.edit(new_fbx=next_fbx, new_door=next_door)
        result = self.publish('door')
        self.assertEqual(self.uploads, ['door'])
        self.assertFalse(result['publicationCurrent']['model'])
        self.assertTrue(result['publicationCurrent']['door'])
        self.assertEqual(result['model_asset_id'], original['model_asset_id'])
        self.assertEqual(result['status'], 'UPDATE_AVAILABLE')
        self.uploads.clear()
        done = self.publish('all')
        self.assertEqual(self.uploads, ['prepare_model','model:house','model:door'])
        self.assertEqual(done['status'], 'PUBLISHED')

    def test_failed_upload_does_not_replace_existing_id(self):
        original = self.start_published()
        next_house = self.root / 'alternate.jpg'; next_house.write_bytes(b'new texture')
        self.edit(new_house=next_house)
        with patch('real_estate.store.prepare_texture', side_effect=self.prepared_image), \
             patch('real_estate.store.create_image_asset', side_effect=RuntimeError('upload interrupted')):
            with self.assertRaisesRegex(RuntimeError, 'upload interrupted'):
                self.store.publish(original['slug'], self.credentials, scope='house')
        pending = self.store.get(original['slug'])
        self.assertEqual(pending['textures']['house']['assetId'], original['textures']['house']['assetId'])
        self.assertFalse(pending['publicationCurrent']['house'])
        self.assertEqual(len(self.store.publications(original['slug'])), 4)

    def test_legacy_bundle_hash_migrates_once_to_model_only_fingerprint(self):
        original = self.start_published()
        with self.store.connect() as db:
            db.execute("UPDATE real_estate SET model_published_hash='legacy-bundle' WHERE slug=?", (original['slug'],))
            db.execute('PRAGMA user_version = 1')
        reopened = RealEstateStore(self.root)
        current = reopened.get(original['slug'])
        self.assertEqual(current['model_published_hash'], current['model_sha256'])
        self.assertEqual(current['status'], 'PUBLISHED')
        with reopened.connect() as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 2)
        alternate = self.root/'alt.png'; alternate.write_bytes(b'after migration')
        self.edit(new_house=alternate)
        self.assertTrue(RealEstateStore(self.root).get(original['slug'])['publicationCurrent']['model'])

    def test_route_forwards_only_requested_scope(self):
        self.start_published()
        replaced = self.root/'updated.png'; replaced.write_bytes(b'updated')
        self.edit(new_house=replaced)
        with patch('real_estate.store.prepare_texture', side_effect=self.prepared_image), \
             patch('real_estate.store.create_image_asset', side_effect=self.upload_image), \
             patch('real_estate.store.wait_for_operation', side_effect=self.await_operation):
            result=real_estate.write('/api/real-estate/house_level1_01/publish',
                lambda:{'scope':'house'}, {'real_estate':self.store,
                 'publication_credentials':lambda desc:self.credentials})
        self.assertEqual(result[0], 200)
        self.assertEqual(self.uploads, ['house'])
        self.assertEqual(result[1]['status'], 'PUBLISHED')

    def test_invalid_scope_rejected_before_any_upload(self):
        with self.assertRaisesRegex(ValueError, 'scope'):
            self.store.publish('house_level1_01', self.credentials, scope='everything')
        self.assertEqual(self.uploads, [])

    def test_ui_contains_independent_controls_and_no_update_api(self):
        script = (ROOT/'system/control-center/static/real-estate.js').read_text('utf-8')
        html = (ROOT/'system/control-center/static/index.html').read_text('utf-8')
        store = (ROOT/'system/control-center/real_estate/store.py').read_text('utf-8')
        self.assertIn('data-re-pub-model', script)
        self.assertIn('data-re-image', script)
        self.assertIn("'image:'+button.dataset.reImage", script)
        self.assertIn('await realEstateRegister()', script)
        self.assertIn('real-estate.js?v=10', html)
        self.assertNotIn('update_model_asset', store)


if __name__ == '__main__':
    unittest.main()
