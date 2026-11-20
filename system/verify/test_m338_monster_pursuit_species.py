"""M338 supersession: M396 migrates territory to each authored spawn point."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'system/control-center'))
from monster_store import MonsterStore
from monster_spawn_store import MonsterSpawnStore

class MonsterPursuitSpeciesTests(unittest.TestCase):
    def test_species_has_aggro_and_attack_but_not_pursuit_radius(self):
        with tempfile.TemporaryDirectory() as d:
            monster=MonsterStore(Path(d))
            npc=MonsterStore(Path(d),kind='npc')
            self.assertEqual(monster._validate_behavior({},None)['aggroRadiusStuds'],16)
            self.assertEqual(npc._validate_behavior({},None)['attackRadiusStuds'],3)
            for store in (monster,npc):
                self.assertNotIn('pursuitRadiusStuds',store._validate_behavior({},None))
    def test_spawn_migration_preserves_position_and_creates_backup(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); path=root/'assets/manifests/monster-spawns.json'
            path.parent.mkdir(parents=True)
            record={'spawnId':'spawn-aaaaaaaaaaaa','monsterSlug':'gremlin','position':{'x':1,'y':2,'z':3},'spawnRadius':15,'maxAlive':3}
            path.write_text(json.dumps({'schemaVersion':1,'project':'game1','records':{record['spawnId']:record}}))
            store=MonsterSpawnStore(root,None,None,None)
            entry=store._load()['records'][record['spawnId']]
            self.assertEqual(entry['position'],record['position'])
            self.assertEqual(entry['homeRadiusStuds'],150)
            self.assertTrue(path.with_suffix('.m396.backup.json').exists())
    def test_spawn_store_keeps_leash_independent_of_spawn_distribution(self):
        row={'homeRadiusStuds':40,'spawnRadius':15,'maxAlive':3,'position':{'x':0,'y':0,'z':0}}
        self.assertEqual(MonsterSpawnStore._core(row)['homeRadiusStuds'],40)
        self.assertEqual(MonsterSpawnStore._core(row)['spawnRadius'],15)
        self.assertNotIn('spawnRadius',MonsterSpawnStore._core(row,npc=True))
    def test_runtime_leash_is_per_spawn_not_species(self):
        initial=(ROOT/'src/server/monster/MonsterInitialAttributes.luau').read_text()
        lifecycle=(ROOT/'src/server/monster/MonsterAgentLifecycle.luau').read_text()
        ui=(ROOT/'system/control-center/static/index.html').read_text()
        self.assertIn('record.homeRadiusStuds',initial)
        self.assertIn('MonsterHomeRadiusStuds',lifecycle)
        self.assertIn('id="monster-spawn-home-radius"',ui)
        self.assertNotIn('id="monster-behavior-pursuit-radius"',ui)

if __name__=='__main__': unittest.main()
