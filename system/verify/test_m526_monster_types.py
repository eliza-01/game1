"""M526 schema, zone geometry/ownership and independent player cap."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services import game_balance as b
from services import balance_patch_logs as logs


def read(path):
    return (ROOT / path).read_text(encoding='utf8')


class MonsterTypes(unittest.TestCase):
    def test_two_complete_branches(self):
        data = b.load()
        self.assertEqual(data['schemaVersion'], 4)
        self.assertEqual(len(data['levels']), 35)
        for kind, offset in [('melee', 0), ('ranged', 35)]:
            rows = [r for r in data['monsters'] if r['type'] == kind]
            self.assertEqual([r['level'] for r in rows], list(range(1, 36)))
            self.assertEqual([r['id'] for r in rows], [f'monster_{i:03}' for i in range(1+offset, 36+offset)])
        for field, value in [('level', 2), ('type', 'ranged'), ('attackRange', 0), ('attackRange', 101)]:
            draft = deepcopy(data)
            draft['monsters'][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                b.validate(draft)
        draft = deepcopy(data)
        draft['monsters'][35]['attackRange'] = 7
        with self.assertRaises(ValueError): b.validate(draft)
        draft = deepcopy(data)
        draft['monsterBindings']['gremlin'] = 'monster_036'
        self.assertEqual(b.validate(draft)['monsterBindings']['gremlin'], 'monster_036')
        self.assertTrue(any(r['patch'] == 526 for r in logs.load()['entries']))

    def test_player_cap_and_selection(self):
        self.assertIn('Balance.MaxLevel = #Registry.levels', read('src/shared/balance/Balance.luau'))
        self.assertIn('level > Balance.MaxLevel', read('src/server/dev/GameplayTestLoadout.luau'))
        ui = read('src/client/dev/GameplayTestController.luau')
        self.assertIn('Balance.MonsterAt(monsterLevel, monsterType)', ui)
        self.assertIn('monsterId=selectedMonster().id', ui)
        service = read('src/server/dev/GameplayTestService.luau')
        self.assertIn('Balance.Monster(request.monsterId)', service)
        self.assertIn('startGroup(s, monster, request.count)', service)
        self.assertIn('s.layout.slots[monster.id].visit', service)

    def test_isolation_gates_all_target_transitions(self):
        policy = read('src/server/monster/MonsterTargetPolicy.luau')
        ai = read('src/server/monster/MonsterAIService.luau')
        attack = read('src/server/monster/MonsterAttackExecutor.luau')
        self.assertIn('Isolation.Allows(agent.model, target)', policy)
        self.assertIn('targetRoot and allowsTarget(agent, character)', policy)
        self.assertIn('not allowsTarget(agent, target)', policy)
        self.assertIn('TargetPolicy.AllowsTarget(agent, agent.target)', ai)
        self.assertIn('not TargetPolicy.AllowsTarget(agent, attacker)', ai)
        self.assertIn('if not Retreat.IsRanged(agent.model) then maintainAttackPursuit', attack)
        self.assertIn('TargetPolicy.AttackStillConnects(agent, target)', attack)
        self.assertIn('if balance then balance.attackRange', read('src/server/monster/MonsterInitialAttributes.luau'))
        self.assertNotIn("Approach.Allows", policy)
        self.assertNotIn("IsStationary", ai)


if __name__ == '__main__': unittest.main()
