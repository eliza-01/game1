"""M115: provenance labels are metadata, not publication or ownership identity."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from location_asset_store import LocationAssetStore
from real_estate.store import RealEstateStore
from test_real_estate_m107 import skeleton


class TextureFilenameCatalogTests(unittest.TestCase):
    def setUp(self):
        work = tempfile.TemporaryDirectory(prefix='m115-texture-labels-')
        self.addCleanup(work.cleanup)
        self.root = Path(work.name)
        self.model = self.root / 'example.fbx'
        self.model.write_bytes(b'fbx')
        self.texture = self.root / 'Granite Atlas (final).png'
        self.texture.write_bytes(b'png-content')
        self.location = LocationAssetStore(self.root)

    def register(self, slug, *, image=None, reuse=None):
        return self.location.register({
            'slug': slug, 'nameEn': 'Granite Wall' if slug == 'granite' else 'Another Prop',
            'category': 'rock', 'modelSourcePath': str(self.model),
            'textureSourcePath': str(image) if image else '',
            'textureReferenceSlug': reuse or '',
        })

    def publish_in_db(self, slug, image_id='99012'):
        with self.location.connect() as conn:
            conn.execute('''UPDATE location_assets SET texture_asset_id=?,
                texture_published_sha256=texture_sha256 WHERE slug=?''', (image_id, slug))

    def test_source_filename_persists_after_canonical_copy_and_edit(self):
        owner = self.register('granite', image=self.texture)
        self.assertTrue(owner['texture_path'].endswith('/granite.png'))
        self.assertEqual(owner['texture_filename'], self.texture.name)
        self.assertIn('Granite Atlas (final).png', self.location.snapshot()['items'][0]['texture_filename'])
        self.publish_in_db('granite')
        before = self.location.get('granite')
        after = self.location.register({'slug':'granite','nameEn':'Granite Wall', 'category':'rock'})
        self.assertEqual(after['texture_filename'], self.texture.name)
        self.assertEqual(after['texture_asset_id'], before['texture_asset_id'])
        self.assertEqual(after['texture_sha256'], before['texture_sha256'])

    def test_shared_texture_uses_owner_filename_and_changes_with_owner(self):
        self.register('granite', image=self.texture)
        shared = self.register('another', reuse='granite')
        self.assertEqual(shared['texture_filename'], 'Granite Atlas (final).png')
        self.assertTrue(shared['texture_shared'])
        other = self.root / 'New_Stone_Atlas.jpg'
        other.write_bytes(b'new-image')
        self.location.register({'slug':'granite','nameEn':'Granite Wall', 'category':'rock',
                                'textureSourcePath':str(other)})
        shared = self.location.get('another')
        self.assertEqual(shared['texture_filename'], other.name)
        self.assertEqual(shared['texture_path'], self.location.get('granite')['texture_path'])
        self.assertEqual(shared['texture_reference_slug'], 'granite')

    def test_migration_legacy_texture_fallback_preserves_published_id(self):
        self.register('granite', image=self.texture)
        self.publish_in_db('granite')
        self.register('another', reuse='granite')
        with self.location.connect() as conn:
            conn.execute('ALTER TABLE location_assets DROP COLUMN texture_filename')
        migrated = LocationAssetStore(self.root)
        owner = migrated.get('granite')
        shared = migrated.get('another')
        self.assertEqual(owner['texture_filename'], 'granite.png')
        self.assertEqual(shared['texture_filename'], 'granite.png')
        self.assertEqual(owner['texture_asset_id'], '99012')
        self.assertEqual(shared['texture_asset_id'], '99012')
        self.assertEqual(shared['texture_owner_slug'], 'granite')

    def test_estate_catalog_contains_source_name_slug_and_stable_reference(self):
        self.register('granite', image=self.texture)
        self.publish_in_db('granite')
        estate = RealEstateStore(self.root, location_assets=self.location)
        refs = estate.texture_references()
        self.assertEqual(len(refs), 1)
        entry = refs[0]
        self.assertEqual(entry['reference'], 'location:granite')
        self.assertEqual(entry['label'], 'Granite Wall')
        self.assertEqual(entry['slug'], 'granite')
        self.assertEqual(entry['filename'], self.texture.name)
        self.assertEqual(entry['assetId'], '99012')

    def test_estate_owned_texture_preserves_filename_on_unrelated_edits(self):
        model = self.root / 'house_level5_01.fbx'
        model.write_bytes(b'estate')
        house = self.root / 'Majestic Villa Atlas.png'
        house.write_bytes(b'atlas')
        door = self.root / 'Handcrafted_Door.jpg'
        door.write_bytes(b'door-texture')
        estate = RealEstateStore(self.root, location_assets=self.location)
        payload = {'sourcePath':str(model),'houseType':'house','level':5,'variant':'01',
                   'textures':{'house':str(house),'door':str(door)},'acceptWarnings':True}
        with patch('real_estate.store.inspect',return_value=skeleton()):
            row = estate.register(payload)
        self.assertEqual(row['textures']['house']['filename'], house.name)
        self.assertEqual(row['textures']['door']['filename'], door.name)
        with estate.connect() as db:
            raw = db.execute('SELECT textures_json FROM real_estate WHERE slug=?',
                             (row['slug'],)).fetchone()[0]
            textures = json.loads(raw)
            for part, item in textures.items():
                item['assetId'] = '101' if part == 'house' else '102'
                item['publishedSha256'] = item['sha256']
                item['publicationFormat'] = 'source'
            db.execute('UPDATE real_estate SET textures_json=? WHERE slug=?',
                       (json.dumps(textures), row['slug']))
        options = estate.texture_references()
        self.assertEqual({(opt['reference'],opt['filename']) for opt in options}, {
            ('estate:house_level5_01:house', house.name),
            ('estate:house_level5_01:door', door.name)})
        row = estate.get('house_level5_01')
        edited = {**payload, 'existingSlug':row['slug'], 'sourcePath':'',
                  'textures':{part:item['path'] for part,item in row['textures'].items()}}
        with patch('real_estate.store.inspect',return_value=skeleton()):
            after = estate.register(edited)
        self.assertEqual(after['textures']['house']['filename'], house.name)
        self.assertEqual(after['textures']['door']['filename'], door.name)
        self.assertEqual(after['textures']['house']['assetId'], '101')
        self.assertEqual(after['textures']['door']['assetId'], '102')

    @unittest.skipUnless(shutil.which('node'), 'Node.js needed for browser-side contract check')
    def test_browser_labels_search_and_asset_blocks(self):
        script = ROOT / 'system/verify/texture_filename_catalog_m115.js'
        result = subprocess.run(['node',str(script)], text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
