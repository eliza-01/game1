"""M385: Real Estate Collision Blueprint v3 stays separate from visual meshes and plots."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from real_estate.store import RealEstateStore
from services.location_collision_blueprint import validate
from services.location_collision_authoring import LocationCollisionAuthoring
from api.real_estate import read as house_read, write as house_write

FRAME = [0,0,0,1,0,0,0,1,0,0,0,1]
PART = {'id':'wall_01','name':'Wall','shape':'Block','size':[2,5,0.5],
        'localCFrame':[3,0,-1,1,0,0,0,1,0,0,0,1],
        'collisionGroup':'Default','canQuery':True,'canTouch':False}
HOUSE_BLUEPRINT = {'schemaVersion':3,'pivot':'Model:GetPivot()','parts':[PART]}


def register_test_house(store, slug='house_level5_01'):
    with store.connect() as db:
        db.execute('''INSERT INTO real_estate
            (slug,house_type,house_level,variant,purchase_price,min_level,sale_price,
             model_path,model_sha256,skeleton_json,textures_json,model_rigs_json,
             revision,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (slug,'house',5,'01',1,1,1,'house.fbx','a'*64,
             json.dumps({'meshes':[{'name':'walls','armature':'house_armature',
               'bones':[{'name':'chimney_01_socket','parent':''}],
               'influencedBones':[]}]}),json.dumps({'walls':{'path':'', 'filename':''}}),
             json.dumps({'rig_carrier':{'assetId':'456789'}}),1,0,0))


class HouseCollisionM385(unittest.TestCase):
    def test_domain_specific_schema_and_shared_part_validation(self):
        self.assertEqual(validate(HOUSE_BLUEPRINT, slug='house_level5_01', domain='house'),HOUSE_BLUEPRINT)
        with self.assertRaises(ValueError):
            validate(HOUSE_BLUEPRINT, slug='stone_fence', domain='location')
        with self.assertRaises(ValueError):
            validate({**HOUSE_BLUEPRINT,'anchor':{'meshId':'11'}},slug='house_level5_01',domain='house')
        for change in [{'shape':'MeshPart'},{'size':[1,0,1]},{'localCFrame':[1]*12}]:
            with self.subTest(change=change),self.assertRaises(ValueError):
                validate({**HOUSE_BLUEPRINT,'parts':[{**PART,**change}]},slug='house_level5_01',domain='house')

    def test_persist_revision_cas_and_reattach_to_same_type(self):
        with tempfile.TemporaryDirectory() as temp:
            store=RealEstateStore(Path(temp))
            register_test_house(store)
            first=store.save_collision_blueprint('house_level5_01',
                {'blueprint':HOUSE_BLUEPRINT,'expectedRevision':0})
            self.assertEqual(first['revision'],1)
            repeated=store.save_collision_blueprint('house_level5_01',
                {'blueprint':HOUSE_BLUEPRINT,'expectedRevision':1})
            self.assertEqual(repeated['revision'],1)
            changed={**HOUSE_BLUEPRINT,'parts':[{**PART,'size':[2,6,0.5]}]}
            with self.assertRaisesRegex(ValueError,'changed since Capture'):
                store.save_collision_blueprint('house_level5_01',{'blueprint':changed,'expectedRevision':0})
            next_revision=store.save_collision_blueprint('house_level5_01',
                {'blueprint':changed,'expectedRevision':1})
            self.assertEqual(next_revision['revision'],2)
            self.assertEqual(len(store.collision_blueprint_history('house_level5_01')),2)
            # House authoring deletion MUST NOT cascade into Plot or collision identity.
            with store.connect() as db:
                db.execute('DELETE FROM real_estate WHERE slug=?',('house_level5_01',))
            self.assertEqual(store.collision_blueprint('house_level5_01')['revision'],2)
            with self.assertRaises(ValueError):
                store.save_collision_blueprint('house_level5_01',
                    {'blueprint':HOUSE_BLUEPRINT,'expectedRevision':2})
            register_test_house(store)
            self.assertEqual(store.collision_blueprint('house_level5_01')['revision'],2)

    def test_studio_capture_only_and_read_routes(self):
        with tempfile.TemporaryDirectory() as temp:
            store=RealEstateStore(Path(temp))
            register_test_house(store)
            calls=[]
            def studio(**kwargs):
                calls.append(kwargs)
                return {'blueprint':HOUSE_BLUEPRINT} if kwargs['phase'] in ('validate','capture') else {'partCount':1}
            service=LocationCollisionAuthoring(store,studio,domain='house')
            self.assertEqual(service.operate('house_level5_01','validate')['revision'],0)
            result=service.operate('house_level5_01','capture')
            self.assertEqual(result['revision'],1)
            self.assertEqual(calls[-1]['domain'],'house')
            self.assertEqual(calls[-1]['expected_house_model_id'],'456789')
            self.assertEqual(service.operate('house_level5_01','preview')['partCount'],1)
            self.assertEqual(calls[-1]['blueprint']['schemaVersion'],3)
            self.assertEqual(service.operate('house_level5_01','clear-preview')['partCount'],1)
            self.assertEqual(calls[-1]['expected_house_model_id'],'')
            path='/api/real-estate/house_level5_01'
            url=lambda suffix: type('URL',(),{'path':path+suffix,'query':''})()
            response=house_read(url('/collision-blueprint'),{'real_estate':store})
            self.assertEqual(response[0],200)
            self.assertEqual(response[1]['revision'],1)
            self.assertEqual(house_read(url('/collision-history'),{'real_estate':store})[1]['history'][0]['partCount'],1)
            deps={'real_estate':store,'house_collision_authoring':service}
            self.assertEqual(house_write(path+'/collision-studio', lambda:{'phase':'validate'},deps)[0],200)
            self.assertEqual(house_write(path+'/collision-studio', lambda:{'phase':'place'},deps)[0],400)
            self.assertEqual(house_write(path+'/collision-studio', lambda:{'phase':'capture','unknown':True},deps)[0],400)

    def test_studio_and_ui_use_canonical_pivot_and_separate_preview(self):
        def read(path): return (ROOT/path).read_text(encoding='utf-8')
        author=read('system/studio-plugin/modules/StudioLocationCollisionAuthoring.luau')
        transform=read('system/studio-plugin/modules/StudioLocationCollisionTransform.luau')
        parts=read('system/studio-plugin/modules/StudioLocationCollisionParts.luau')
        house=read('system/studio-plugin/modules/StudioRealEstateModel.luau')
        sync=read('system/control-center/real_estate/studio_sync.py')
        page=read('system/control-center/static/index.html')
        view=read('system/control-center/static/location-collision.js')
        self.assertIn('root:GetPivot()',author)
        self.assertIn('house-collision-authoring-v1',author)
        self.assertIn('Game1PlotHousePreview',author)
        self.assertIn('PREVIEW_HOUSE',author)
        self.assertIn('schemaVersion == 3',transform)
        self.assertIn('Game1HouseCollisionOwned',parts)
        self.assertIn('CollisionParts.Prepare(wrapper',house)
        self.assertIn('CollisionParts.Prepare(root',house)
        self.assertIn('houseCollisionFailures = houseCollisionFailures',house)
        self.assertIn("stats.get('houseCollisionFailures', 0) != 0",sync)
        self.assertIn("'collisionBlueprint': collision['blueprint']",sync)
        self.assertIn('house-collision-panel',page)
        self.assertIn("attach('house-collision','real-estate'",view)
        self.assertNotIn('root:PivotTo(',author)

if __name__=='__main__': unittest.main()
