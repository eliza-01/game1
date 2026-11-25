"""M523: Database owns player AS; seeded ratios and no bow reload.
Live editor values intentionally remain editable, not hard-coded invariants.
"""
from copy import deepcopy
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services import game_balance as b
from services import balance_patch_logs as logs


class InterludeBalance(unittest.TestCase):
    def test_base_speed_is_validated_and_projected(self):
        data = b.load()
        self.assertEqual(b.OUTPUT.read_text(encoding='utf8'), b.render(data))
        for invalid in (24, 401, 180.5, float('nan'), True):
            draft = deepcopy(data)
            draft['rules']['baseAttackSpeed'] = invalid
            with self.assertRaises(ValueError):
                b.validate(draft)
        draft = deepcopy(data)
        del draft['rules']['baseAttackSpeed']
        with self.assertRaises(ValueError):
            b.validate(draft)
        draft = deepcopy(data)
        draft['rules']['baseAttackSpeed'] = 190
        self.assertIn('["baseAttackSpeed"] = 190,', b.render(draft))

    def test_seed_math_and_rounding_budget(self):
        speeds = [math.floor(180 * n / 379 + .5) for n in (379, 433, 325, 293)]
        self.assertEqual(speeds, [180, 206, 154, 139])
        ratios = (1, 246/281, 342/281, 180/139)
        for sword in (20, 31, 45, 63, 80, 103, 125, 147):
            attacks = [math.floor(sword * r + .5) for r in ratios]
            for attack, ratio, speed in zip(attacks, ratios, speeds):
                self.assertLessEqual(abs(attack - sword*ratio), .5)
                self.assertLessEqual(abs(attack*speed/(sword*180) - ratio*speed/180), speed/(2*sword*180) + 1e-9)
            self.assertLessEqual(abs(attacks[3]*139/300 - sword*180/300), 139/600 + 1e-9)
        self.assertEqual([math.floor(80*r+.5) for r in ratios], [80,70,97,104])
        self.assertGreater(581/281*139/180, 1.59)

    def test_server_client_cadence_and_database_ownership(self):
        def read(path): return (ROOT / path).read_text(encoding='utf8')
        service = read('src/server/character/CharacterStatsService.luau')
        self.assertIn('setBase(character, "AttackSpeed", Balance.Rules.baseAttackSpeed)', service)
        self.assertNotIn('value("AttackSpeed")', service)
        self.assertIn('AttackSpeed = Balance.Rules.baseAttackSpeed', read('src/shared/character/CharacterStatsConfig.luau'))
        self.assertIn('AttackSpeed = stats.attackSpeedDelta', read('src/server/weapon/WeaponEquipService.luau'))
        for path in ('src/server/combat/AttackService.luau','src/client/character/animation/CharacterAnimationController.luau'):
            self.assertIn('AttackTimelineConfig.ResolveCharacterRuntime(clipId, character:GetAttribute("AttackSpeed"))', read(path))
        self.assertIn('local attackDuration = timing.duration', read('src/server/combat/AttackService.luau'))
        self.assertIn('AttackSessionStore.Begin(player, character, serial, clientAttackId, now + attackDuration)', read('src/server/combat/AttackService.luau'))

    def test_log_and_documentation(self):
        entries = logs.load()['entries']
        self.assertEqual(entries[0]['patch'], 520)
        self.assertTrue(any(row['patch'] == 523 and 'L2' in row['message'] for row in entries))
        self.assertTrue((ROOT/'docs/workflows/M523_INTERLUDE_WEAPON_BALANCE_RU.md').is_file())
