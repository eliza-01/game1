"""M411: pin existing published LOD1 across both asset domains without republishing."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlparse
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from location_asset_store import LocationAssetStore
from real_estate.store import RealEstateStore
from api.read_world import route as read_world
from api.write_world import route as write_world
from api.real_estate import write as write_house
from services.lod_reuse_catalog import library, confirmed_source


class SharedLodReuseM411(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.locations = LocationAssetStore(self.root)
        self.houses = RealEstateStore(self.root, location_assets=self.locations)
        fb = self.root/'asset.fbx'
        fb.write_bytes(b'; FBX 7.4.0\nFBXHeaderExtension: {}\nFULL')
        self.source = self.locations.register({'nameEn':'Source Post', 'category':'fence',
            'modelSourcePath':str(fb),'appearanceMode':'material'})['slug']
        self.target = self.locations.register({'nameEn':'Other Post', 'category':'fence',
            'modelSourcePath':str(fb),'appearanceMode':'material'})['slug']
        self.house = 'house_level5_01'
        with self.houses.connect() as db:
            db.execute('''INSERT INTO real_estate (
                slug,house_type,house_level,variant,purchase_price,min_level,sale_price,
                model_path,model_sha256,skeleton_json,textures_json,model_rigs_json,
                revision,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (self.house,'house',5,'01',1,1,1,'house.fbx','a'*64,
                 json.dumps({'meshes':[{'name':'house','armature':'house_armature',
                    'bones':[{'name':'house_floor_01_spawn_socket','parent':''}],
                    'influencedBones':[]}]}),json.dumps({'house':{'path':'','filename':''}}),json.dumps({}),1,0,0))
        self.lod_file=self.root / f'{self.source}_lod1.fbx'
        self.lod_file.write_bytes(b'; FBX 7.4.0\nFBXHeaderExtension: {}\nLOD1')
        self.locations.stage_lod1(self.source, str(self.lod_file), 0)
        with self.locations.connect() as db:
            db.execute('''UPDATE location_asset_lod_resources SET asset_id=?,published_sha256=?,moderation_state=?
                WHERE asset_slug=?''',('123456789012345',self.locations.get(self.source)['lod1']['sourceSha256'],
                'Approved',self.source))
        self.stores={'location':self.locations,'house':self.houses}

    def payload(self, domain, slug, rev, asset_id, expected_revision=0):
        return {'sourceDomain':domain, 'sourceSlug':slug, 'sourceRevision':rev,
                'sourceModelAssetId':asset_id, 'expectedRevision':expected_revision}

    def test_catalog_and_read_api(self):
        result=library(self.stores)
        self.assertEqual(result,[{'domain':'location','slug':self.source,
            'revision':1,'modelAssetId':'123456789012345'}])
        http, data=read_world(urlparse('/api/lod1-library'),
                             {'location_assets':self.locations,'real_estate':self.houses},lambda:{})
        self.assertEqual((http,data['items']),(200,result))

    def test_location_to_location_pins_id_and_exports_runtime_registry(self):
        source=confirmed_source(self.stores,'location',self.source,1,'123456789012345')
        old=self.locations.get(self.target)
        with patch('services.model_lod_common.create_model_asset') as upload:
            result=self.locations.reuse_lod1(self.target,source,0)
            upload.assert_not_called()
        self.assertEqual(result['status'],'PUBLISHED')
        self.assertEqual(result['modelAssetId'],'123456789012345')
        self.assertEqual(result['reuse'],{'domain':'location','slug':self.source,'revision':1})
        target=self.locations.get(self.target)
        self.assertEqual(target['model_sha256'],old['model_sha256'])
        self.assertEqual(target['model_asset_id'],old['model_asset_id'])
        lua=(self.root/'src/shared/world/LocationAssetRegistry.luau').read_text()
        self.assertIn('lod1ModelAssetId = "123456789012345"',lua)
        self.assertEqual(len(self.locations.lod1_history(self.target)),0) # No fake publication.
        self.assertEqual(self.locations.publish_lod1(self.target,1,{})['status'],'PUBLISHED')
        self.assertEqual(library(self.stores)[0]['slug'],self.source) # No chains.
        self.assertEqual(len(library(self.stores)),1)

    def test_location_source_to_house(self):
        source=confirmed_source(self.stores,'location',self.source,1,'123456789012345')
        result=self.houses.reuse_lod1(self.house,source,0)
        self.assertEqual(result['status'],'PUBLISHED')
        self.assertEqual(result['modelAssetId'],'123456789012345')
        self.assertEqual(self.houses.get(self.house)['lod1']['reuse']['slug'],self.source)
        self.assertEqual(self.houses.publish_lod1(self.house,1,{})['status'],'PUBLISHED')
        with self.houses.connect() as db:
            db.execute('UPDATE real_estate SET model_sha256=? WHERE slug=?',('b'*64,self.house))
        self.assertEqual(self.houses.get(self.house)['lod1']['status'],'FULL_CHANGED')

    def test_house_source_to_location(self):
        with self.houses.connect() as db:
            db.execute('''INSERT INTO real_estate_lod1
                (house_slug,source_path,source_sha256,full_source_sha256,published_sha256,
                 asset_id,moderation_state,revision,updated_at)
                 VALUES(?,?,?,?,?,?,?,?,?)''',
                (self.house,'house_lod1.fbx','f'*64,'a'*64,'f'*64,
                 '987654321098765','Approved',1,0))
        (self.root/'house_lod1.fbx').write_bytes(b'LOD1')
        from services.model_lod_common import sha256
        digest=sha256(self.root/'house_lod1.fbx')
        with self.houses.connect() as db:
            db.execute('UPDATE real_estate_lod1 SET source_sha256=?,published_sha256=? WHERE house_slug=?',
                       (digest,digest,self.house))
        source=confirmed_source(self.stores,'house',self.house,1,'987654321098765')
        bound=self.locations.reuse_lod1(self.target,source,0)
        self.assertEqual(bound['modelAssetId'],'987654321098765')
        self.assertEqual(bound['reuse']['domain'],'house')

    def test_pinned_id_is_independent_from_future_owner_publication(self):
        source=confirmed_source(self.stores,'location',self.source,1,'123456789012345')
        self.locations.reuse_lod1(self.target,source,0)
        with self.locations.connect() as db:
            db.execute('UPDATE location_asset_lod_resources SET asset_id=? WHERE asset_slug=?',
                       ('111111111111111',self.source))
        self.assertEqual(self.locations.get(self.target)['lod1']['modelAssetId'],'123456789012345')
        with self.assertRaisesRegex(ValueError,'changed'):
            confirmed_source(self.stores,'location',self.source,1,'123456789012345')

    def test_modified_published_source_is_not_offered(self):
        staged_path=self.root/self.locations.get(self.source)['lod1']['sourcePath']
        staged_path.write_bytes(b'; FBX 7.4.0\nFBXHeaderExtension: {}\nCHANGED')
        self.assertEqual(library(self.stores),[])
        with self.assertRaisesRegex(ValueError,'changed'):
            confirmed_source(self.stores,'location',self.source,1,'123456789012345')

    def test_restaging_identical_bytes_from_reuse_removes_binding(self):
        source=confirmed_source(self.stores,'location',self.source,1,'123456789012345')
        target=self.locations.reuse_lod1(self.target,source,0)
        path=self.root/f'{self.target}_lod1.fbx'
        path.write_bytes(self.lod_file.read_bytes())
        restaged=self.locations.stage_lod1(self.target,str(path),target['revision'])
        self.assertIsNone(restaged['reuse'])
        self.assertEqual(restaged['revision'],2)

    def test_safe_rejection_stale_self_and_arbitrary_ids(self):
        self.assertRaisesRegex(ValueError,'source',confirmed_source,self.stores,'location','bad_slug',1,'123')
        source=confirmed_source(self.stores,'location',self.source,1,'123456789012345')
        with self.assertRaisesRegex(ValueError,'own'):
            self.locations.reuse_lod1(self.source,source,1)
        with self.assertRaisesRegex(ValueError,'changed'):
            self.locations.reuse_lod1(self.target,source,4)
        with self.assertRaisesRegex(ValueError,'source'):
            confirmed_source(self.stores,'location',self.source,1,'246813579')
        with self.assertRaisesRegex(ValueError,'source'):
            confirmed_source(self.stores,'other',self.source,1,'123456789012345')

    def test_restaging_switches_from_reuse_without_losing_full(self):
        source=confirmed_source(self.stores,'location',self.source,1,'123456789012345')
        reused=self.locations.reuse_lod1(self.target,source,0)
        path=self.root/f'{self.target}_lod1.fbx'
        path.write_bytes(b'; FBX 7.4.0\nFBXHeaderExtension: {}\nNEW LOD1')
        staged=self.locations.stage_lod1(self.target,str(path),reused['revision'])
        self.assertIsNone(staged['reuse'])
        self.assertEqual(staged['status'],'UPDATE_AVAILABLE')
        self.assertTrue(staged['sourcePath'].endswith('lod1.fbx'))

    def test_both_http_mutations(self):
        p=self.payload('location',self.source,1,'123456789012345')
        deps={'location_assets':self.locations,'real_estate':self.houses,
              'deco_layouts':None, 'locations':None, 'monster_spawns':None,
              'npc_place_spawn':None, 'npc_register_spawn':None,
              'npc_spawns':None,'options_store':None,
              'publication_credentials':lambda _: {},'request_active_studio_save':None,
              'run_timeline_editor_bridge':None,'sync_monster_to_studio':None,'timelines':None}
        status,result=write_world('/api/location-assets/'+self.target+'/lod1-reuse',lambda:p,deps)
        self.assertEqual((status,result['status']),(200,'PUBLISHED'))
        self.assertEqual(write_world('/api/location-assets/'+self.target+'/lod1-reuse',lambda:p,deps)[0],400)
        status,result=write_house('/api/real-estate/'+self.house+'/lod1-reuse',lambda:p,deps)
        self.assertEqual(status,200,result)
        self.assertEqual(result['lod1']['status'],'PUBLISHED')


if __name__ == '__main__':
    unittest.main()
