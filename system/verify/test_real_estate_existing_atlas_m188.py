"""Explicit reuse accepts a different published atlas; resolution controls do not."""
import copy
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'system/control-center'))
from real_estate.store import RealEstateStore
from api.real_estate import write
from test_real_estate_m107 import skeleton


class ExistingAtlas(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.store = RealEstateStore(self.root)
        self.first = self.variant('restoration_01_16x16_atlas.png', '111')
        self.second = self.variant('structures_01_16x16_atlas.png', '222')
        self.unpublished = self.variant('structures_02_16x16_atlas.png', '')
        source = self.root/'house_level5_01.fbx'
        source.write_bytes(b'model source')
        analysis = skeleton()
        detail = copy.deepcopy(analysis['meshes'][0])
        detail['name'] = 'structures_01'
        analysis['meshes'].append(detail)
        payload = {'houseType':'house', 'level':5, 'variant':'01', 'sourcePath':str(source),
                   'textures':{}, 'textureReferences':{name:f'atlas:{self.first["id"]}'
                       for name in ('house','door','structures_01')}}
        with patch('real_estate.store.inspect', return_value=analysis):
            self.row = self.store.register(payload)
        self.slug = self.row['slug']

    def variant(self, name, asset_id):
        path = self.root/name
        Image.new('RGBA',(16,16),'red').save(path)
        variant = self.store.atlases.register_file(str(path))
        if asset_id:
            with self.store.atlases.connect() as db:
                db.execute('UPDATE texture_atlas_variants SET published_id=?,published_sha256=source_sha256 WHERE id=?',
                           (asset_id,variant['id']))
        return variant

    def test_existing_rebinds_only_selected_mesh_without_upload(self):
        before = self.store.get(self.slug)
        revision = before['textures']['structures_01']['atlasBindingRevision']
        with patch('real_estate.store.create_image_asset') as estate_upload, \
             patch('real_estate.store.create_model_asset') as model_upload, \
             patch('services.texture_atlas_registry.create_image_asset') as atlas_upload:
            result = self.store.select_atlas(self.slug, 'structures_01', self.second['id'],
                                            revision, mode='existing')
            estate_upload.assert_not_called()
            model_upload.assert_not_called()
            atlas_upload.assert_not_called()
        self.assertEqual(result['textures']['structures_01']['assetId'], '222')
        for name in ('house','door'):
            self.assertEqual(result['textures'][name], before['textures'][name])
        self.assertEqual(result['rigAssets'], before['rigAssets'])
        self.assertEqual(result['model_sha256'], before['model_sha256'])
        self.assertEqual(result['skeleton'], before['skeleton'])

    def test_resolution_mode_keeps_series_guard_and_stale_reuse_is_rejected(self):
        revision = self.row['textures']['structures_01']['atlasBindingRevision']
        with self.assertRaisesRegex(ValueError, 'same mesh series'):
            self.store.select_atlas(self.slug, 'structures_01', self.second['id'], revision)
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.store.select_atlas(self.slug, 'structures_01', self.second['id'], revision+1, mode='existing')
        with self.assertRaisesRegex(ValueError, 'published'):
            self.store.select_atlas(self.slug, 'structures_01', self.unpublished['id'], revision, mode='existing')
        with self.assertRaisesRegex(ValueError, 'unknown atlas selection mode'):
            self.store.select_atlas(self.slug, 'structures_01', self.second['id'], revision, mode='anything')
        self.assertEqual(self.store.get(self.slug)['textures']['structures_01']['assetId'], '111')

    def test_api_preserves_selected_binding_if_studio_is_offline(self):
        payload = {'part':'structures_01', 'variantId':self.second['id'], 'mode':'existing',
                   'expectedRevision':self.row['textures']['structures_01']['atlasBindingRevision']}
        def offline(*args):
            raise RuntimeError('Studio offline')
        status, result = write('/api/real-estate/'+self.slug+'/atlas-binding', lambda:payload,
                              {'real_estate':self.store, 'sync_real_estate_to_studio':offline})
        self.assertEqual(status,200)
        self.assertEqual(result['studioSyncStatus'],'pending_studio_sync')
        self.assertEqual(self.store.get(self.slug)['textures']['structures_01']['assetId'],'222')


if __name__ == '__main__':
    unittest.main()
