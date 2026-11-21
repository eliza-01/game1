"""M412: per-part house LOD1 is shared geometry with per-part appearance."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'system/control-center'))
from real_estate.store import RealEstateStore
from location_asset_store import LocationAssetStore
from services.lod_reuse_catalog import library, confirmed_source
from services.house_runtime_profile import DEFAULT
from api.real_estate import write as write_house
from api.read_world import route as read_world
from urllib.parse import urlparse

HOUSE='house_level5_01'
PART='wall'


def register_house(store):
    skeleton={'meshes':[{'name':PART,'armature':'house_armature', 'bones':[{'name':'house_floor_01_spawn_socket','parent':''}], 'influencedBones':[]}]}
    with store.connect() as db:
        db.execute('''INSERT INTO real_estate(
            slug,house_type,house_level,variant,purchase_price,min_level,sale_price,
            model_path,model_sha256,skeleton_json,textures_json,model_rigs_json,
            revision,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (HOUSE,'house',5,'01',1,1,1,'house.fbx','a'*64,json.dumps(skeleton),
             json.dumps({PART:{'path':'','filename':''}}),json.dumps({}),1,0,0))


class HousePartLodM412(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.locations=LocationAssetStore(self.root)
        self.store=RealEstateStore(self.root,location_assets=self.locations)
        register_house(self.store)
        self.fbx=self.root/(HOUSE+'_'+PART+'_lod1.fbx')
        self.fbx.write_bytes(b'Kaydara FBX Binary  \x00\x1a\x00' + b'geometry')

    def publish(self):
        staged=self.store.stage_part_lod1(HOUSE,PART,str(self.fbx),0)
        with patch('services.house_part_lod_resource.publish_geometry',
                   return_value=SimpleNamespace(asset_id='1234567890',moderation_state='Approved')):
            return self.store.publish_part_lod1(HOUSE,PART,staged['revision'],{})

    def test_schema_additive_and_legacy_lod_stays_readable(self):
        with self.store.connect() as db:
            self.assertIsNotNone(db.execute("SELECT name FROM sqlite_master WHERE name='real_estate_lod1'").fetchone())
            self.assertIsNotNone(db.execute("SELECT name FROM sqlite_master WHERE name='real_estate_part_lod1'").fetchone())
        from services.house_part_lod_resource import ensure_schema
        ensure_schema(self.store);ensure_schema(self.store)
        self.assertEqual(self.store.get(HOUSE)['partLod1'][PART]['status'],'NOT_REGISTERED')
        self.assertEqual(self.store.get(HOUSE)['lod1']['status'],'NOT_REGISTERED')

    def test_upload_uses_common_publisher_and_unlocks_only_own_part(self):
        with self.assertRaisesRegex(ValueError,'at least one'):
            self.store.save_runtime_profile(HOUSE,{**DEFAULT,'mode':'lod1'},0)
        part=self.publish()
        self.assertEqual(part['modelAssetId'],'1234567890')
        self.assertEqual(self.store.get(HOUSE)['partLod1'][PART]['status'],'PUBLISHED')
        profile=self.store.save_runtime_profile(HOUSE,{**DEFAULT,'mode':'lod1'},0)
        self.assertEqual(profile['mode'],'lod1')
        self.assertEqual(self.store.get(HOUSE)['lod1']['status'],'NOT_REGISTERED')
        self.assertTrue(self.store.get(HOUSE)['runtimeReadiness']['warnings']) # FULL not published in fixture
        self.fbx.write_bytes(b'different')
        # staged copy is immutable: changing the selected original file has no effect.
        self.assertEqual(self.store.get(HOUSE)['partLod1'][PART]['status'],'PUBLISHED')
        with self.store.connect() as db:
            db.execute('UPDATE real_estate SET model_sha256=? WHERE slug=?', ('b'*64,HOUSE))
        self.assertEqual(self.store.get(HOUSE)['partLod1'][PART]['status'],'FULL_CHANGED')

    def test_reuse_source_is_pinned_and_no_extra_upload(self):
        self.publish()
        stores={'house':self.store,'house_part':self.store,'location':self.locations}
        sources=library(stores)
        item=next(x for x in sources if x['domain']=='house_part')
        self.assertEqual(item['slug'],HOUSE+'/'+PART)
        confirmed=confirmed_source(stores,'house_part',item['slug'],item['revision'],item['modelAssetId'])
        self.assertEqual(confirmed['modelAssetId'],'1234567890')
        with self.assertRaisesRegex(ValueError,'cannot reuse own'):
            self.store.reuse_part_lod1(HOUSE,PART,confirmed,1)
        with self.assertRaisesRegex(ValueError,'revision'):
            confirmed_source(stores,'house_part',item['slug'],0,item['modelAssetId'])

    def test_shared_library_read_api_and_part_write_api(self):
        self.publish()
        status,data=read_world(urlparse('/api/lod1-library'),{
            'location_assets':self.locations,'real_estate':self.store},lambda:{})
        self.assertEqual(status,200)
        self.assertIn(HOUSE+'/'+PART,[i['slug'] for i in data['items']])
        deps={'real_estate':self.store,'location_assets':self.locations,
              'publication_credentials':lambda description:{}}
        path=f'/api/real-estate/{HOUSE}/parts/{PART}/lod1-reuse'
        self.assertEqual(write_house(path,lambda: {},deps)[0],400)
        self.assertEqual(write_house(f'/api/real-estate/{HOUSE}/parts/unknown/lod1-stage',
                            lambda:{'sourcePath':str(self.fbx),'expectedRevision':0},deps)[0],400)

    def test_cross_domain_house_part_to_location_and_location_to_house_part(self):
        part=self.publish()
        stores={'house':self.store,'house_part':self.store,'location':self.locations}
        src=confirmed_source(stores,'house_part',HOUSE+'/'+PART,part['revision'],part['modelAssetId'])
        full=self.root/'source.fbx'
        full.write_bytes(b'Kaydara FBX Binary  \x00\x1a\x00full')
        slug=self.locations.register({'nameEn':'Lamp Part', 'category':'light',
            'modelSourcePath':str(full),'appearanceMode':'material'})['slug']
        reused=self.locations.reuse_lod1(slug,src,0)
        self.assertEqual(reused['status'],'PUBLISHED')
        self.assertEqual(reused['modelAssetId'],part['modelAssetId'])
        # A new publishing revision on the origin must not mutate the pinned consumer.
        with self.store.connect() as db:
            db.execute('UPDATE real_estate_part_lod1 SET asset_id=? WHERE house_slug=? AND part_name=?',
                       ('7654321098',HOUSE,PART))
        self.assertEqual(self.locations.get(slug)['lod1']['modelAssetId'],'1234567890')

    def test_unpublished_house_parts_are_intentionally_unloaded(self):
        from services.house_runtime_profile import readiness
        house=self.store.get(HOUSE)
        house['meshParts']=[PART, 'chimney']
        house['partStreaming']['chimney']={'lod1':100,'hide':350,'revision':0}
        slots={PART: {'status':'PUBLISHED','modelAssetId':'123456'},
               'chimney': {'status':'NOT_REGISTERED','modelAssetId':''}}
        result=readiness(house,{**DEFAULT,'mode':'lod1'},slots)
        # Missing LOD1 for another part is optional, not a reason to publish 28 FBXs.
        self.assertFalse(any('chimney' in message for message in result['warnings']))
        self.assertTrue(any('Publish all house' in message for message in result['warnings']))
        none=readiness(house,{**DEFAULT,'mode':'lod1'}, {})
        self.assertTrue(any('at least one' in message for message in none['warnings']))
        unfinished=readiness(house,{**DEFAULT,'mode':'lod1'},
                             {PART:{'status':'FULL_CHANGED'},'chimney':{'status':'PUBLISHED'}})
        self.assertTrue(any('FULL_CHANGED' in message for message in unfinished['warnings']))

    def test_reused_model_cache_keeps_color_per_house_part(self):
        server=(ROOT/'src/server/world/LocationLodTemplateService.luau').read_text()
        client=(ROOT/'src/client/world/HouseVisualAdapter.luau').read_text()
        contract=(ROOT/'src/shared/world/LocationRuntimeManifestContract.luau').read_text()
        self.assertIn('local partIdsAttempted = {}',server)
        self.assertIn('partIdsAttempted[name] = true',server)
        self.assertIn('"__HOUSE_PART_LOD1__" .. tostring(spec.lod1ModelAssetId)',server)
        self.assertIn('"__HOUSE_PART_LOD1__" .. tostring(spec.lod1ModelAssetId)',client)
        self.assertIn('Appearance.Apply(lod, {',client)
        self.assertIn('if spec.lod1ModelAssetId == "" then continue end',server)
        self.assertIn('if profile.mode == "lod1" and lodParts == 0 then',contract)

    def test_source_files_and_existing_full_untouched(self):
        prior=self.store.get(HOUSE)['model_sha256']
        result=self.store.stage_part_lod1(HOUSE,PART,str(self.fbx),0)
        self.assertTrue((self.root/result['sourcePath']).exists())
        self.assertEqual(self.store.get(HOUSE)['model_sha256'],prior)
        self.assertEqual(self.store.get(HOUSE)['partLod1'][PART]['revision'],1)
        with self.assertRaisesRegex(ValueError,'changed'):
            self.store.stage_part_lod1(HOUSE,PART,str(self.fbx),0)

if __name__=='__main__':unittest.main()
