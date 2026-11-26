"""M549: Database owns species defaults, spawn owns overrides, GP uses Database."""
from copy import deepcopy
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services import game_balance as b
from monster_spawn_store import MonsterSpawnStore, REQUIRED_ANIMATION_SLOTS

class Monsters:
    def __init__(self):
        self.rows = {slug: {'slug':slug, 'status':'PUBLISHED', 'model_asset_id':'123',
                            'behavior':{'aggressive':False,'aggroRadiusStuds':17.5}}
                     for slug in ('gremlin','unbound')}
    def get(self, slug): return self.rows.get(slug)
    def list(self): return list(self.rows.values())

class Animations:
    def list_for_monster(self, slug):
        return [{'slot':slot,'status':'PUBLISHED'} for slot in REQUIRED_ANIMATION_SLOTS]

def bridge(action, **kwargs):
    return {'position':{'x':1,'y':2,'z':3}, 'yawDegrees':0, 'placeId':0,'mapKey':'main'}

def read(path): return (ROOT/path).read_text(encoding='utf8')

class MonsterAggro(unittest.TestCase):
    def setUp(self):
        self.data = deepcopy(b.load())
        self.data['monsterBindings']={'gremlin':'monster_001'}
        for row in self.data['monsters']:
            if row['nameEn']=='Toad': row.update(aggressive=True, aggroRadiusStuds=22.5)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.project(self.data)
        self.store=MonsterSpawnStore(self.root, Monsters(), Animations(), bridge)
    def project(self,data):
        source=self.root/'config/balance/gameplay.json';output=self.root/'src/shared/balance/BalanceRegistry.luau'
        source.parent.mkdir(parents=True,exist_ok=True);output.parent.mkdir(parents=True,exist_ok=True)
        source.write_text(json.dumps(data),encoding='utf8');output.write_text(b.render(data),encoding='utf8')
    def test_database_validation_and_projection(self):
        for k,v in [('aggressive',0),('aggressive','true'),('aggroRadiusStuds',-1),('aggroRadiusStuds',10001),('aggroRadiusStuds',True),('aggroRadiusStuds',float('nan'))]:
            bad=deepcopy(self.data);bad['monsters'][0][k]=v
            with self.assertRaises(ValueError):b.validate(bad)
        self.assertEqual(b.load(self.root),self.data)
        self.assertIn('["aggroRadiusStuds"] = 22.5',b.render(self.data))
    def test_spawn_defaults_override_and_registry(self):
        rows={r['slug']:r for r in self.store.snapshot()['monsters']}
        self.assertEqual((rows['gremlin']['aggressive'],rows['gremlin']['aggroRadiusStuds']),(True,22.5))
        self.assertEqual((rows['unbound']['aggressive'],rows['unbound']['aggroRadiusStuds']),(False,17.5))
        draft=self.store.place({'monsterSlug':'gremlin'})['draft']
        self.assertTrue(draft['aggressive']);self.assertEqual(draft['aggroRadiusStuds'],22.5)
        draft.update(aggressive=False,aggroRadiusStuds=0)
        record=self.store.register(draft)['record']
        self.assertFalse(record['aggressive']);self.assertEqual(record['aggroRadiusStuds'],0)
        persisted=self.store._load()['records'][record['spawnId']]
        self.assertEqual(self.store._core(persisted)['aggroRadiusStuds'],0)
        self.assertIs(self.store._core(persisted)['aggressive'],False)
        registry=(self.root/'src/server/monster/MonsterSpawnRegistry.luau').read_text()
        self.assertIn('"aggressive":false',registry);self.assertIn('"aggroRadiusStuds":0.0',registry)
        self.assertEqual(self.store._fingerprint(persisted),self.store._fingerprint({**persisted,'aggroRadiusStuds':99,'aggressive':True}))
        for row in self.data['monsters']:
            if row['nameEn']=='Toad': row['aggroRadiusStuds']=50
        self.project(self.data)
        self.assertEqual(self.store.snapshot()['records'][0]['aggroRadiusStuds'],0)
        self.assertEqual(self.store.place({'monsterSlug':'gremlin'})['draft']['aggroRadiusStuds'],50)
        for bad in ({'aggressive':'false'},{'aggroRadiusStuds':-1},{'aggroRadiusStuds':None}):
            with self.assertRaises(ValueError):self.store.place({'monsterSlug':'gremlin',**bad})
    def test_legacy_unoverridden_spawn_and_npc(self):
        row=self.store.place({'monsterSlug':'gremlin'})['draft']
        row.pop('aggressive');row.pop('aggroRadiusStuds')
        manifest=self.store._load();manifest['records'][row['spawnId']]=row;self.store._commit(manifest)
        self.assertNotIn('aggroRadiusStuds',self.store._core(row))
        self.assertEqual(self.store.snapshot()['records'][0]['aggroRadiusStuds'],22.5)
        self.assertNotIn('aggroRadiusStuds',self.store._core({**row,'aggroRadiusStuds':0},npc=True))
    def test_runtime_and_hud_contract(self):
        runtime=read('src/server/monster/MonsterInitialAttributes.luau')
        for token in ('balance.aggressive','balance.aggroRadiusStuds','type(record.aggressive) == "boolean"','record.aggroRadiusStuds ~= nil','record.testKind ~= "zone"','record.testZone == 8'):
            self.assertIn(token,runtime)
        self.assertNotIn('HuntingPlan.Aggro',read('src/server/dev/GameplayTestLayout.luau'))
        self.assertNotIn('testAggroRadius',read('src/server/dev/GameplayTestArena.luau'))
        self.assertEqual(sum(s['duration']==600 and s['id'].endswith('_d') for s in b.load()['skills']),4)
        self.assertIn('string.format("%d:%02d"',read('src/client/combat/BuffHud.luau'))
        self.assertIn("input.type='checkbox';input.checked=row[key]",read('system/control-center/static/game-balance.js'))
        self.assertIn('numberField("Aggro radius · studs", "aggroRadiusStuds"',read('system/studio-plugin/modules/StudioMonsterSpawnAuthoring.luau'))
