"""M127: Estate is a consumer of M125's shared atlas identity, not an image publisher."""
from __future__ import annotations
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

from PIL import Image
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from real_estate.store import RealEstateStore
from real_estate.studio_sync import RealEstateStudioSync
from api.real_estate import write
from test_real_estate_m107 import skeleton


class RealEstateCentralAtlasTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'incoming'
        self.source.mkdir()
        self.fbx = self.source / 'house_level2_01.fbx'
        self.fbx.write_bytes(b'model for house level2')
        self.large = self.source / 'house_level2_01_128x128_atlas.png'
        self.small = self.source / 'house_level2_01_64x64_atlas.png'
        Image.new('RGBA', (128,128), (100,40,10,90)).save(self.large)
        Image.new('RGBA', (64,64), (50,80,20,120)).save(self.small)
        self.store = RealEstateStore(self.root)

    def payload(self, variant='01', **other):
        return dict(houseType='house', level=2, variant=variant,
                    sourcePath=str(self.fbx),
                    textures={'house':str(self.large), 'door':''},
                    textureReferences={'door':'mesh:house'}, **other)

    def register(self, payload):
        with mock.patch('real_estate.store.inspect', return_value=skeleton()):
            return self.store.register(payload)

    def publish_id(self, variant_id, image_id):
        with self.store.atlases.connect() as db:
            db.execute('UPDATE texture_atlas_variants SET published_id=?,published_sha256=source_sha256 WHERE id=?',
                       (image_id,variant_id))

    def test_registration_preserves_level_variant_and_shared_door_image(self):
        row=self.register(self.payload())
        self.assertEqual(row['slug'],'house_level2_01')
        self.assertEqual(row['textures']['house']['filename'],'house_level2_01_128x128_atlas.png')
        self.assertEqual(row['textures']['door']['reuseReference'],'mesh:house')
        self.assertEqual(row['textures']['door']['atlasVariantId'],row['textures']['house']['atlasVariantId'])
        self.assertFalse(row['textures']['house']['atlasLegacyWarning'])
        self.publish_id(row['textures']['house']['atlasVariantId'],'8001')
        row=self.store.get(row['slug'])
        self.assertEqual(row['textures']['house']['assetId'],'8001')
        self.assertEqual(row['textures']['door']['assetId'],'8001')
        self.assertTrue(row['publicationCurrent']['house'])
        self.assertTrue(row['publicationCurrent']['door'])
        self.assertFalse(row['publicationCurrent']['model'])

    def test_switch_resolution_only_selected_mesh_no_upload_and_keep_model_id(self):
        row=self.register(self.payload())
        large_id=row['textures']['house']['atlasVariantId']
        small=self.store.atlases.register_file(str(self.small))
        self.publish_id(large_id,'8001')
        self.publish_id(small['id'],'8002')
        with self.store.connect() as db:
            rigs={'house':{'assetId':'9001','publishedSha256':row['model_sha256']},
                  'door':{'assetId':'9002','publishedSha256':row['model_sha256']}}
            db.execute('UPDATE real_estate SET model_rigs_json=?,model_asset_id=?,model_published_hash=? WHERE slug=?',
                (json.dumps(rigs),'9001',row['model_sha256'],row['slug']))
        before=self.store.get(row['slug'])
        self.assertEqual(before['status'],'PUBLISHED')
        with mock.patch('services.texture_atlas_registry.create_image_asset') as atlas_upload, \
             mock.patch('real_estate.store.create_image_asset') as estate_upload:
            result=self.store.select_atlas(row['slug'],'house',small['id'],expected_revision=1)
            result=self.store.publish(row['slug'], {'apiKey':'','creatorType':'User','creatorId':'1'}, scope='image:house')
            atlas_upload.assert_not_called()
            estate_upload.assert_not_called()
        self.assertEqual(result['textures']['house']['assetId'],'8002')
        self.assertEqual(result['textures']['door']['assetId'],'8002')
        self.assertEqual(result['rigAssets'],before['rigAssets'])
        self.assertEqual(result['status'],'PUBLISHED')
        self.assertEqual(result['textures']['house']['atlasBindingRevision'],2)
        with self.assertRaisesRegex(ValueError,'stale'):
            self.store.select_atlas(row['slug'],'house',large_id,expected_revision=1)
        # Independent mesh selection breaks only its own reuse link.
        door=self.store.select_atlas(row['slug'],'door',large_id,expected_revision=0)
        self.assertEqual(door['textures']['door']['assetId'],'8001')
        self.assertEqual(door['textures']['house']['assetId'],'8002')
        self.assertEqual(door['rigAssets'],before['rigAssets'])
        self.assertEqual(door['textures']['door']['reuseReference'],'')
        self.assertEqual(door['status'],'PUBLISHED')
        # Stale sync acknowledgement must not hide later changes.
        self.assertFalse(self.store.atlases.mark_synced('real_estate','house_level2_01:house',1))

    def test_second_estate_reuses_published_variant_without_upload(self):
        first=self.register(self.payload())
        vid=first['textures']['house']['atlasVariantId']
        self.publish_id(vid,'8001')
        other=self.source/'house_level2_02.fbx'
        other.write_bytes(b'another house model')
        payload=self.payload(variant='02')
        payload['sourcePath']=str(other)
        payload['textures']={'house':'','door':''}
        payload['textureReferences']={'house':f'atlas:{vid}','door':'mesh:house'}
        with mock.patch('services.texture_atlas_registry.create_image_asset') as uploaded:
            row=self.register(payload)
            self.store.publish(row['slug'],{'apiKey':'','creatorType':'User','creatorId':'1'},scope='image:house')
            uploaded.assert_not_called()
        self.assertEqual(row['textures']['house']['assetId'],'8001')
        self.assertEqual(row['textures']['door']['assetId'],'8001')
        self.assertEqual(row['status'],'UPDATE_AVAILABLE')
        self.assertEqual(self.store.get('house_level2_01')['textures']['house']['assetId'],'8001')

    def test_studio_ack_is_per_mesh_and_api_degrades_to_pending(self):
        row=self.register(self.payload())
        vid=row['textures']['house']['atlasVariantId']
        self.publish_id(vid,'8001')
        with self.store.connect() as db:
            rigs={'house':{'assetId':'9001','publishedSha256':row['model_sha256']},
                  'door':{'assetId':'9002','publishedSha256':row['model_sha256']}}
            db.execute('UPDATE real_estate SET model_rigs_json=?,model_asset_id=?,model_published_hash=? WHERE slug=?',
                (json.dumps(rigs),'9001',row['model_sha256'],row['slug']))
        stub=lambda *a,**kw:{'destination':'ServerStorage.house_level2_01','realEstateStats':{
            'bonesValidated':True,'rigsValidated':2,'texturesApplied':2}}
        done=RealEstateStudioSync(self.store,stub).sync(row['slug'])
        self.assertEqual(done['studio']['destination'],'ServerStorage.house_level2_01')
        self.assertEqual(self.store.atlases.binding('real_estate','house_level2_01:house')['syncStatus'],'synced')
        small=self.store.atlases.register_file(str(self.small))
        self.publish_id(small['id'],'8002')
        sync_attempts=[]
        def broken(slug):
            sync_attempts.append(slug)
            raise RuntimeError('Studio offline')
        route=f'/api/real-estate/{row["slug"]}/atlas-binding'
        code,payload=write(route,lambda:{'part':'house','variantId':small['id'],'expectedRevision':1},
                           {'real_estate':self.store,'sync_real_estate_to_studio':broken})
        self.assertEqual(code,200)
        self.assertEqual(sync_attempts,[row['slug']])
        self.assertEqual(payload['studioSyncStatus'],'pending_studio_sync')
        self.assertEqual(self.store.get(row['slug'])['textures']['house']['assetId'],'8002')
        self.assertEqual(self.store.atlases.binding('real_estate','house_level2_01:house')['syncStatus'],'pending_studio_sync')

    def test_old_filename_keeps_published_metadata_and_warns(self):
        path=self.source/'house.png'
        Image.new('RGB',(16,16),'red').save(path)
        payload=self.payload()
        payload['textures']['house']=str(path)
        row=self.register(payload)
        self.assertTrue(row['textures']['house']['atlasLegacyWarning'])
        self.assertIsNone(row['textures']['house']['atlasVariantId'])
        self.assertEqual(self.store.atlases.catalog(),[])
