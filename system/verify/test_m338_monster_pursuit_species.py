"""M338 per-species pursuit contract and migration regressions."""
from pathlib import Path
import json
import sqlite3
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system' / 'control-center'))
sys.path.insert(0, str(ROOT / 'system' / 'verify'))
from monster_store import MonsterStore
from monster_spawn_store import MonsterSpawnStore
from m338_migrate_monster_pursuit import run as migrate


class MonsterPursuitSpeciesTests(unittest.TestCase):
    def test_monster_behavior_validation_is_independent_from_npc(self):
        with tempfile.TemporaryDirectory() as temp:
            store = MonsterStore(Path(temp))
            defaults = store._validate_behavior({}, None)
            self.assertEqual(defaults['pursuitRadiusStuds'], 150)
            self.assertEqual(defaults['aggroRadiusStuds'], 16)
            self.assertEqual(store._validate_behavior({'behavior': {'pursuitRadiusStuds': 250}}, None)['pursuitRadiusStuds'], 250)
            for bad in (-1, 0, 10001, float('nan'), float('inf')):
                with self.assertRaises(ValueError):
                    store._validate_behavior({'behavior': {'pursuitRadiusStuds': bad}}, None)
            npc = MonsterStore(Path(temp), kind='npc')
            self.assertEqual(npc._validate_behavior({}, None)['pursuitRadiusStuds'], 16)

    def test_migration_preserves_ids_and_species_values(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = MonsterStore(root)
            with store.connect() as conn:
                conn.execute("INSERT INTO monsters(slug,name_en,model_asset_id,model_published_sha256,model_sha256,created_at,updated_at) VALUES (?,?,?,?,?,?,?)", ('gremlin','Gremlin','123456789','abc','abc',0,0))
                conn.execute("INSERT INTO monster_behavior(monster_slug,aggressive,aggro_radius_studs,attack_radius_studs,rise_from_ground,pursuit_radius_studs) VALUES (?,?,?,?,?,?)", ('gremlin',1,32,5,0,220))
            store.export()
            spawn = root / 'assets/manifests/monster-spawns.json'
            spawn.parent.mkdir(parents=True,exist_ok=True)
            spawn.write_text(json.dumps({'schemaVersion':1,'project':'game1','records':{'spawn-test':{'spawnId':'spawn-test','monsterSlug':'gremlin','position':{'x':1,'y':2,'z':3},'homeRadiusStuds':40,'spawnRadius':15,'maxAlive':3}}}))
            backup = migrate(root)
            self.assertTrue((backup / 'game1.db').exists())
            self.assertEqual(MonsterStore(root).get('gremlin')['behavior']['pursuitRadiusStuds'],220)
            self.assertEqual(MonsterStore(root).get('gremlin')['model_asset_id'],'123456789')
            self.assertNotIn('homeRadiusStuds', spawn.read_text())
            self.assertIn('pursuitRadiusStuds = 220', (root / 'src/shared/monster/MonsterRegistry.luau').read_text())
            self.assertNotIn('homeRadiusStuds', (root / 'src/server/monster/MonsterSpawnRegistry.luau').read_text())
            # Repeat migration; custom radii and original authored spawn stay unchanged.
            migrate(root)
            self.assertEqual(MonsterStore(root).get('gremlin')['behavior']['pursuitRadiusStuds'],220)
            self.assertIn('"spawnRadius": 15', spawn.read_text())

    def test_spawn_store_keeps_npc_radius_but_drops_monster_leash(self):
        source = {'spawnId':'spawn-aaaaaaaaaaaa','monsterSlug':'gremlin','homeRadiusStuds':40,'spawnRadius':15,'maxAlive':3,'position':{'x':0,'y':0,'z':0}}
        self.assertNotIn('homeRadiusStuds', MonsterSpawnStore._core(source))
        self.assertEqual(MonsterSpawnStore._core(source,npc=True)['homeRadiusStuds'],40)

    def test_luau_uses_per_type_radius_not_spawn_area(self):
        ai = (ROOT / 'src/server/monster/MonsterAIService.luau').read_text()
        initial = (ROOT / 'src/server/monster/MonsterInitialAttributes.luau').read_text()
        lifecycle = (ROOT / 'src/server/monster/MonsterAgentLifecycle.luau').read_text()
        ui = (ROOT / 'system/control-center/static/index.html').read_text()
        self.assertIn('withinPursuitRadius(agent, agent.root.Position)', ai)
        self.assertIn('withinPursuitRadius(agent, targetRoot.Position)', ai)
        self.assertIn('behavior.pursuitRadiusStuds', initial)
        self.assertIn('MonsterPursuitRadiusStuds', lifecycle)
        self.assertNotIn('MonsterHomeRadiusStuds', initial+lifecycle)
        self.assertIn('id="monster-behavior-pursuit-radius"', ui)
        self.assertNotIn('id="monster-spawn-home-radius"', ui)


if __name__ == '__main__':
    unittest.main()
