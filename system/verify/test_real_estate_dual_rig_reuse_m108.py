"""M108: independent Real Estate rigs, shared texture references and safe migration."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from real_estate.store import RealEstateStore
from real_estate.contracts import assert_rig_survived
from real_estate.studio_sync import RealEstateStudioSync
from test_real_estate_m107 import skeleton


class LocationStub:
    def __init__(self, path):
        self.path = path
        self.asset_id = '99001'
        self.current = True
    def list(self):
        return [{'slug':'stone-wall','name_en':'Stone Wall',
                 'texture_path':str(self.path), 'texture_sha256':'owner-sha',
                 'texture_asset_id':self.asset_id,
                 'texture_published_sha256':('owner-sha' if self.current else 'pending-sha')}]


class DualRigReuseTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='m108-test-')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        folder = self.root / 'source';folder.mkdir()
        self.fbx = folder / 'house_level1_01.fbx';self.fbx.write_bytes(b'fbx')
        self.house = folder / 'house.png';self.house.write_bytes(b'house')
        self.door = folder / 'door.jpg';self.door.write_bytes(b'door')
        self.location = LocationStub(self.house.relative_to(self.root))
        self.store = RealEstateStore(self.root, location_assets=self.location)
        self.payload = {'sourcePath':str(self.fbx), 'houseType':'house','level':1,'variant':'01',
                        'textures':{'house':str(self.house),'door':str(self.door)}}
        with patch('real_estate.store.inspect',return_value=skeleton()):
            self.store.register(self.payload)
        self.ids = iter(range(800001,800100))
        self.uploads = []

    def stage(self, root, source, target, expected, textures):
        self.assertEqual({*textures},{'house','door'})
        self.assertEqual(len(expected['meshes']),2)
        target.mkdir(parents=True)
        for part in ('house','door'):
            (target / (part + '.fbx')).write_bytes(part.encode('utf8'))

    def image(self, root, part, source, stage):
        return source

    def upload_model(self, path, **kwargs):
        self.assertEqual(path.suffix,'.fbx')
        self.assertIn(path.stem,('house','door'))
        self.assertEqual(kwargs['display_name'].split()[-1],path.stem)
        self.uploads.append('model:'+path.stem)
        return 'operations/'+path.stem

    def upload_image(self, path, **kwargs):
        part = kwargs['display_name'].split()[-1]
        self.uploads.append('image:'+part)
        return 'operations/'+part

    def wait(self, operation, **kwargs):
        return SimpleNamespace(asset_id=str(next(self.ids)),moderation_state='Approved',operation_path=operation)

    def publish(self, *, scope='all', upload_model=None):
        credentials={'apiKey':'test','creatorType':'user','creatorId':'1'}
        with patch('real_estate.store.prepare_publication',side_effect=self.stage), \
             patch('real_estate.store.prepare_texture',side_effect=self.image), \
             patch('real_estate.store.create_model_asset',side_effect=upload_model or self.upload_model), \
             patch('real_estate.store.create_image_asset',side_effect=self.upload_image), \
             patch('real_estate.store.wait_for_operation',side_effect=self.wait):
            return self.store.publish('house_level1_01',credentials,scope=scope)

    def test_independent_published_rigs_and_fresh_ids(self):
        row=self.publish()
        self.assertEqual(self.uploads,['model:house','model:door','image:house','image:door'])
        self.assertEqual(row['status'],'PUBLISHED')
        self.assertNotEqual(row['rigAssets']['house']['assetId'],row['rigAssets']['door']['assetId'])
        self.assertEqual(row['rigAssets']['house']['assetId'],row['model_asset_id'])
        self.assertEqual({p['part'] for p in self.store.publications(row['slug'])},
                         {'model:house','model:door','house','door'})
        self.uploads.clear()
        self.publish()
        self.assertEqual(self.uploads,[])

    def test_partial_model_failure_retries_only_unpublished_rig(self):
        def failing(path, **kwargs):
            if path.stem=='door':
                raise RuntimeError('door upload interrupted')
            return self.upload_model(path,**kwargs)
        with self.assertRaisesRegex(RuntimeError,'door upload interrupted'):
            self.publish(scope='model',upload_model=failing)
        row=self.store.get('house_level1_01')
        first_house_id=row['rigAssets']['house']['assetId']
        self.assertNotIn('door',row['rigAssets'])
        self.assertFalse(row['publicationCurrent']['model'])
        self.uploads.clear()
        row=self.publish(scope='model')
        self.assertEqual(self.uploads,['model:door'])
        self.assertEqual(row['rigAssets']['house']['assetId'],first_house_id)
        self.assertTrue(row['publicationCurrent']['model'])

    def test_legacy_single_asset_requires_two_rig_republication(self):
        with self.store.connect() as db:
            db.execute("UPDATE real_estate SET model_asset_id='12345',model_published_hash=model_sha256")
        row=self.store.get('house_level1_01')
        self.assertEqual(row['model_asset_id'],'12345')
        self.assertFalse(row['publicationCurrent']['model'])
        self.publish(scope='model')
        updated=self.store.get('house_level1_01')
        self.assertNotEqual(updated['rigAssets']['house']['assetId'],'12345')
        self.assertTrue(updated['publicationCurrent']['model'])

    def test_reuse_location_asset_published_image_without_upload(self):
        edit={**self.payload,'sourcePath':'', 'existingSlug':'house_level1_01',
              'textures':{'house':'','door':str(self.door)},
              'textureReferences':{'house':'location:stone-wall','door':''}}
        row=self.store.register(edit)
        self.assertEqual(row['textures']['house']['assetId'],'99001')
        self.assertTrue(row['publicationCurrent']['house'])
        self.assertEqual(row['textures']['house']['reuseReference'],'location:stone-wall')
        self.publish(scope='all')
        self.assertNotIn('image:house',self.uploads)
        self.assertIn('image:door',self.uploads)
        self.location.asset_id='99002'
        refreshed=self.store.get('house_level1_01')
        self.assertEqual(refreshed['textures']['house']['assetId'],'99002')
        self.location.current=False
        self.assertFalse(self.store.get('house_level1_01')['publicationCurrent']['house'])
        with self.assertRaisesRegex(ValueError,'owner must publish'):
            self.publish(scope='house')

    def test_reject_unavailable_self_or_bogus_reuse(self):
        for reference in ('location:missing','estate:house_level1_01:house','../bad'):
            with self.subTest(ref=reference):
                edit={**self.payload,'existingSlug':'house_level1_01','sourcePath':'',
                    'textureReferences':{'house':reference},
                    'textures':{'house':'','door':str(self.door)}}
                with self.assertRaisesRegex(ValueError,'reusable texture'):
                    self.store.register(edit)

    def test_published_estate_texture_can_be_reused_independently(self):
        self.publish()
        second={**self.payload,'existingSlug':'','sourcePath':str(self.fbx),
                'variant':'02','textureReferences':{'house':'estate:house_level1_01:house'},
                'textures':{'house':'','door':str(self.door)}}
        with patch('real_estate.store.inspect',return_value=skeleton()):
            row=self.store.register(second)
        self.assertEqual(row['textures']['house']['assetId'],
                         self.store.get('house_level1_01')['textures']['house']['assetId'])
        self.assertEqual(row['textures']['house']['reuseReference'],'estate:house_level1_01:house')
        self.assertTrue(row['publicationCurrent']['house'])

    def test_single_rig_geometry_and_bones_are_validated_independently(self):
        both=skeleton()
        only={'schemaVersion':1,'meshes':[both['meshes'][0]]}
        assert_rig_survived(both,only,'house')
        wrong={'schemaVersion':1,'meshes':[both['meshes'][1]]}
        with self.assertRaises(ValueError):
            assert_rig_survived(both,wrong,'house')
        missing=json.loads(json.dumps(only))
        missing['meshes'][0]['bones'].pop()
        with self.assertRaisesRegex(ValueError,'bone names'):
            assert_rig_survived(both,missing,'house')
        pose=json.loads(json.dumps(only))
        pose['meshes'][0]['bones'][0]['matrixLocal'][0]=100.0
        with self.assertRaisesRegex(ValueError,'rest pose'):
            assert_rig_survived(both,pose,'house')

    def test_studio_requires_both_ids_and_both_rigs(self):
        row=self.publish()
        calls=[]
        def load(*args,**kwargs):
            calls.append((args,kwargs))
            return {'destination':'ServerStorage.real_estate.house_level1_01.model.house_level1_01',
                    'realEstateStats':{'bonesValidated':True,'rigsValidated':2,'texturesApplied':2}}
        service=RealEstateStudioSync(self.store,load)
        service.sync('house_level1_01')
        self.assertEqual(calls[0][0][0],row['rigAssets']['house']['assetId'])
        self.assertEqual(calls[0][1]['metadata']['doorModelAssetId'],row['rigAssets']['door']['assetId'])
        plugin=(ROOT/'system/studio-plugin/modules/StudioRealEstateModel.luau').read_text('utf-8')
        self.assertIn('part:sub(1, 1):upper()',plugin)
        self.assertIn('metadata.rigAssetIds',plugin)
        self.assertIn('local parts = orderedParts(manifests)',plugin)
        self.assertIn('verifyRig',plugin)

    def test_ui_offers_vertical_reuse_with_registered_texture_catalog(self):
        js=(ROOT/'system/control-center/static/real-estate.js').read_text('utf-8')
        css=(ROOT/'system/control-center/static/real-estate.css').read_text('utf-8')
        self.assertIn('real-estate-reuse-',js)
        self.assertIn('real-estate-reference-',js)
        self.assertIn('textureReferences:',js)
        self.assertIn('flex-direction:column',css)
        self.assertIn('Published Location/Real Estate Image Asset',js)
        self.assertIn('real-estate.js?v=10',(ROOT/'system/control-center/static/index.html').read_text('utf-8'))

if __name__=='__main__':
    unittest.main()
