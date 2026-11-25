"""M527 canonical seed ratios, editable speed and single recovery owner."""
from copy import deepcopy
from pathlib import Path
import math
import sys
import unittest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services import game_balance as b
from services import balance_patch_logs as logs

def read(path): return (ROOT / path).read_text(encoding='utf8')

class RangedRetreat(unittest.TestCase):
    def test_seed(self):
        data = b.load()
        # Design examples; the live table remains freely editable.
        for hp, damage, expected_hp, expected_damage in ((96,10,106,13),(576,84,634,109),(1086,170,1195,220)):
            self.assertEqual(math.floor(hp * 1.1 + .5), expected_hp)
            self.assertEqual(math.floor(damage * 180/139 + .5), expected_damage)
        self.assertEqual(math.floor(100 * 139/180 + .5), 77)
        self.assertEqual(data['schemaVersion'], 4)
        self.assertEqual(b.OUTPUT.read_text(encoding='utf8'), b.render(data))
        self.assertTrue(any(x['patch'] == 527 for x in logs.load()['entries']))

    def test_speed_validation(self):
        data = b.load()
        for val in (0, 401, float('nan'), 77.5):
            draft = deepcopy(data); draft['monsters'][35]['attackSpeed'] = val
            with self.assertRaises(ValueError): b.validate(draft)
        draft = deepcopy(data); draft['monsters'][35]['attackSpeed'] = 90
        self.assertIn('["attackSpeed"] = 90,', b.render(draft))
        self.assertIn('if balance then balance.attackSpeed', read('src/server/monster/MonsterInitialAttributes.luau'))
        self.assertIn("'attackRange','attackSpeed'", read('system/control-center/static/game-balance.js'))

    def test_recovery_ownership(self):
        attack = read('src/server/monster/MonsterAttackExecutor.luau')
        ai = read('src/server/monster/MonsterAIService.luau')
        retreat = read('src/server/monster/MonsterRangedRetreat.luau')
        life = read('src/server/monster/MonsterAgentLifecycle.luau')
        self.assertIn('rule.stat ~= "AttackSpeed"', attack)
        self.assertIn('percent * finite(agent.model:GetAttribute("AttackSpeed"), 100) / 100', attack)
        self.assertIn('cycleDuration = timing.duration', attack)
        self.assertIn('now + math.max(duration, cycleDuration)', attack)
        self.assertIn('if not Retreat.IsRanged(agent.model) then maintainAttackPursuit', attack)
        self.assertIn('not agent.attacking and targetRoot and Retreat.Step', ai)
        self.assertIn('or Retreat.Waiting(agent) then return end', ai)
        self.assertGreaterEqual(ai.count('Retreat.Clear(agent)'), 3)
        self.assertEqual(life.count('Retreat.Clear(agent)'), 2)
        self.assertIn('TargetPolicy.HorizontalDelta(target, position)', retreat)
        self.assertIn('reach - away.Magnitude - STOP_DISTANCE', retreat)
        self.assertIn('HomeLeash.Outside', retreat)
        self.assertIn('Workspace:Raycast', retreat)
        self.assertNotIn('Navigation.NavigateTo', retreat)
        self.assertIn('agent.humanoid:MoveTo(point)', retreat)

if __name__ == '__main__': unittest.main()
