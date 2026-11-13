"""M337 source/serialization regressions; Roblox Studio runtime remains manual QA."""
from pathlib import Path
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system' / 'control-center'))
from options_store import OptionsStore, normalize_monster_ai, normalize_npc_overhead
from monster_spawn_store import MonsterSpawnStore


class M337Tests(unittest.TestCase):
    def test_npc_overhead_independent_devices(self):
        result = normalize_npc_overhead({'mobile': {'nameRadiusStuds': 80}},
                                         {'desktop': {'nameRadiusStuds': 70, 'healthRadiusStuds': 70},
                                          'mobile': {'nameRadiusStuds': 70, 'healthRadiusStuds': 70}})
        self.assertEqual(result['desktop']['nameRadiusStuds'], 70)
        self.assertEqual(result['mobile']['nameRadiusStuds'], 80)
        self.assertEqual(result['mobile']['healthRadiusStuds'], 70)

    def test_npc_overhead_rejects_invalid(self):
        for value in (float('nan'), 0, 801, -1, '70'):
            with self.assertRaises(ValueError):
                normalize_npc_overhead({'mobile': {'nameRadiusStuds': value}})

    def test_monster_timer_validation(self):
        self.assertEqual(normalize_monster_ai({})['noDamageReturnSeconds'], 30)
        for value in (float('inf'), 0, 3601):
            with self.assertRaises(ValueError):
                normalize_monster_ai({'noDamageReturnSeconds': value})

    def test_existing_options_preserved_by_migration(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = root / 'assets/manifests/options.json'
            target.parent.mkdir(parents=True)
            source = json.loads((ROOT / 'assets/manifests/options.json').read_text())
            source.pop('npcOverhead', None)
            source.pop('monsterAi', None)
            source['healthUi']['mobile']['monster']['width'] = 157
            source['camera']['mobileLookSpeed'] = 2.25
            target.write_text(json.dumps(source), encoding='utf-8')
            stored = OptionsStore(root).snapshot()
            self.assertEqual(stored['healthUi']['mobile']['monster']['width'], 157)
            self.assertEqual(stored['camera']['mobileLookSpeed'], 2.25)
            self.assertEqual(stored['npcOverhead']['desktop']['nameRadiusStuds'], 70)
            self.assertEqual(stored['monsterAi']['noDamageReturnSeconds'], 30)
            generated = (root / 'src/shared/GameOptionsRegistry.luau').read_text()
            self.assertIn('npcOverhead', generated)
            self.assertIn('monsterAi', generated)

    def test_spawn_runtime_home_radius_and_marker_fingerprint(self):
        source = {'spawnId': 'spawn-' + 'a' * 12, 'monsterSlug': 'gremlin',
                  'position': {'x': 1, 'y': 2, 'z': 3}, 'respawnSeconds': 10,
                  'homeRadiusStuds': 110}
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            path = root / 'assets/manifests/monster-spawns.json'
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({'schemaVersion': 1, 'project': 'game1',
                                        'records': {source['spawnId']: source}}), encoding='utf-8')
            store = MonsterSpawnStore(root, None, None, None)
            out = (root / 'src/server/monster/MonsterSpawnRegistry.luau').read_text()
            self.assertNotIn('homeRadiusStuds', out)
            first = store._fingerprint(source)
            second = store._fingerprint({**source, 'homeRadiusStuds': 120})
            self.assertEqual(first, second)  # changing leash does not stale marker
            self.assertNotIn('homeRadiusStuds', store._core(source))
            self.assertEqual(store._core(source, npc=True)['homeRadiusStuds'], 110)

    def test_runtime_npc_conditions_and_ai_owner(self):
        client = (ROOT / 'src/client/combat/NpcOverheadController.luau').read_text()
        self.assertIn('hp < maxHP - 0.001 or hostile', client)
        self.assertIn('view.SetSegments(', client)
        self.assertIn('distSq <= nameSq', client)
        self.assertIn('distSq <= hpSq', client)
        ai = (ROOT / 'src/server/monster/MonsterAIService.luau').read_text()
        self.assertIn('GameOptions.MonsterNoDamageReturnSeconds()', ai)
        self.assertIn('onDamageDealt', ai)
        self.assertIn('withinPursuitRadius(agent, targetRoot.Position)', ai)
        self.assertIn('agent.returning then', ai)
        self.assertIn('if not aggressive(agent) and not agent.retaliating and not agent.returning', ai)

    def test_compact_options_preserve_controls(self):
        html = (ROOT / 'system/control-center/static/index.html').read_text()
        self.assertEqual(html.count('class="game1-option-section"'), 6)
        for key in ('option-combat-state-duration', 'health-ui-fields', 'option-camera-save',
                    'option-npc-device', 'option-monster-return-time', 'option-published-debug-buttons',
                    'monster-behavior-pursuit-radius', 'npc-spawn-home-radius'):
            self.assertIn(f'id="{key}"', html)


if __name__ == '__main__':
    unittest.main()
