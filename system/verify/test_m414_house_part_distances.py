"""M414: one distance owner per part, safe migration and Runtime serialization."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'system/control-center'))
from services.house_part_distances import validate, ensure_schema
from services.house_runtime_compilation import inspect, payload, fingerprint
from real_estate.store import RealEstateStore
from api.real_estate import write as write_house
from test_m388_house_runtime_integration import selected, build_source
from xml.etree import ElementTree as ET

HOUSE='house_level5_01'


def fixture(store):
    analysis={'meshes':[{'name':'walls_outside','armature':'house_armature','bones':[{'name':'house_floor_01_spawn_socket','parent':''}], 'influencedBones':[]},
                        {'name':'roof','armature':'house_armature','bones':[{'name':'house_floor_01_spawn_socket','parent':''}], 'influencedBones':[]}]}
    with store.connect() as db:
        db.execute('''INSERT INTO real_estate(slug,house_type,house_level,variant,
          purchase_price,min_level,sale_price,model_path,model_sha256,skeleton_json,
          textures_json,model_rigs_json,mesh_options_json,revision,created_at,updated_at)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
          (HOUSE,'house',5,'01',1,1,1,'house.fbx','a'*64,json.dumps(analysis),
           json.dumps({'roof':{'path':'','filename':''},'walls_outside':{'path':'','filename':''}}),json.dumps({}),json.dumps({
             'walls_outside':{'distanceStreaming':True,'loadDistanceStuds':95,'noCollide':True},
             'roof':{'distanceStreaming':False,'loadDistanceStuds':80,'noCollide':True}}),1,0,0))
        db.execute('''INSERT INTO real_estate_streaming_profiles
            (house_slug,mode,lod1,hide,hysteresis,revision) VALUES (?,?,?,?,?,?)''',
            (HOUSE,'full',180,600,10,2))


class HouseDistancesM414(unittest.TestCase):
    def test_migration_keeps_custom_values_and_retired_fields_disappear(self):
        with tempfile.TemporaryDirectory() as directory:
            store=RealEstateStore(Path(directory));fixture(store)
            ensure_schema(store)
            row=store.get(HOUSE)
            self.assertEqual(row['runtimeProfile'],{'mode':'full','revision':2})
            self.assertEqual(row['partStreaming']['walls_outside']['lod1'],95)
            self.assertEqual(row['partStreaming']['walls_outside']['hide'],600)
            self.assertEqual(row['partStreaming']['roof']['lod1'],180)
            with store.connect() as db:
                raw=json.loads(db.execute('SELECT mesh_options_json FROM real_estate WHERE slug=?',(HOUSE,)).fetchone()[0])
                self.assertEqual(raw['walls_outside']['noCollide'],True)
                self.assertNotIn('loadDistanceStuds',raw['walls_outside'])
                count=db.execute('SELECT COUNT(*) FROM real_estate_part_distances').fetchone()[0]
            self.assertEqual(count,2)
            saved=store.save_part_distances(HOUSE,'roof',{'lod1':240,'hide':750},1)
            self.assertEqual(saved['revision'],2)
            with self.assertRaisesRegex(ValueError,'changed'):
                store.save_part_distances(HOUSE,'roof',{'lod1':270,'hide':850},1)
            ensure_schema(store)
            self.assertEqual(store.get(HOUSE)['partStreaming']['roof']['lod1'],240)
            self.assertEqual(store.get(HOUSE)['partStreaming']['walls_outside']['lod1'],95)
            with self.assertRaisesRegex(ValueError,'unknown visual'):
                store.save_part_distances(HOUSE,'other',{'lod1':50,'hide':350},0)

    def test_validation_and_revision_reject_unsafe_changes(self):
        for row in ({'lod1':40,'hide':50},{'lod1':20,'hide':40},
                    {'lod1':100,'hide':10001},{'lod1':True,'hide':300},
                    {'lod1':120.5,'hide':300},{'lod1':200,'hide':100},
                    {'lod1':200,'hide':300,'hysteresis':10}):
            with self.subTest(row=row),self.assertRaises(ValueError): validate(row)
        self.assertEqual(validate({'lod1':70,'hide':300}),{'lod1':70,'hide':300})

    def test_http_endpoint_only_updates_one_part(self):
        with tempfile.TemporaryDirectory() as directory:
            store=RealEstateStore(Path(directory));fixture(store);ensure_schema(store)
            status, response=write_house(f'/api/real-estate/{HOUSE}/parts/roof/distances',
                lambda:{'distances':{'lod1':210,'hide':850},'expectedRevision':1},
                {'real_estate':store})
            self.assertEqual(status,200,response)
            self.assertEqual(response['distances']['revision'],2)
            self.assertEqual(store.get(HOUSE)['partStreaming']['roof']['lod1'],210)
            self.assertEqual(store.get(HOUSE)['partStreaming']['walls_outside']['lod1'],95)
            code, _=write_house(f'/api/real-estate/{HOUSE}/parts/roof/distances',
                lambda:{'distances':{'lod1':220,'hide':900},'expectedRevision':1},
                {'real_estate':store})
            self.assertEqual(code,400)

    def test_compiled_parts_independent_from_house_pivot_and_profiles(self):
        with tempfile.TemporaryDirectory() as directory:
            source=build_source(Path(directory)/'place/game1_runtime_source.rbxlx')
            entries=selected()
            found=inspect(ET.parse(source),entries)
            packed=payload(found,entries)['types'][HOUSE]
            self.assertEqual(set(packed),{'mode','parts'})
            values={row['name']:row for row in packed['parts']}
            self.assertEqual(values['door']['lod1From'],150)
            self.assertEqual(values['window_frames_glass']['lod1From'],50)
            self.assertEqual(values['window_frames_glass']['hideFrom'],400)
            self.assertNotIn('distance',values['door'])
            entries[HOUSE]['house'].update(revision=1,model_sha256='a'*64,rigAssets={})
            baseline=fingerprint(entries)
            entries[HOUSE]['house']['partStreaming']['door']['hide']=800
            self.assertNotEqual(baseline,fingerprint(entries))
            changed=payload(inspect(ET.parse(source),entries),entries)['types'][HOUSE]['parts']
            self.assertEqual(next(p['hideFrom'] for p in changed if p['name']=='door'),800)

    def test_client_uses_independent_transition_without_a_second_loop(self):
        adapter=(ROOT/'src/client/world/HouseVisualAdapter.luau').read_text()
        policy=(ROOT/'src/shared/world/LocationLodDistancePolicy.luau').read_text()
        contract=(ROOT/'src/shared/world/LocationRuntimeManifestContract.luau').read_text()
        ui=(ROOT/'system/control-center/static/real-estate.js').read_text()
        cache=(ROOT/'src/client/world/LodThresholdCache.luau').read_text()
        self.assertIn('policy.ResolveHouse(distance, previous, record.distances)',cache)
        self.assertIn('policy.SurfaceDistance(position, record.worldFrame, record.worldSize)',cache)
        self.assertNotIn('house.desired',adapter)
        self.assertIn('spec.lod1From',adapter)
        self.assertIn('spec.hideFrom',adapter)
        self.assertIn('Policy.ValidHysteresis',policy)
        self.assertIn('hysteresis=hysteresis',adapter)
        self.assertIn('part.lod1From',contract)
        self.assertIn('part.hideFrom',contract)
        self.assertNotIn('realEstateState.distance',ui)
        self.assertEqual(adapter.count('RunService.Heartbeat:Connect'),0)
