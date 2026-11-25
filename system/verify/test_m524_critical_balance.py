"""Database contract, authoritative critical resolution and transient GP modifiers."""
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


class CriticalBalance(unittest.TestCase):
    def test_schema_round_trip_and_bounds(self):
        data = b.load()
        for group in ('weapons', 'monsters'):
            for invalid in (-1, 50.01, float('nan'), float('inf'), True, '12', None):
                draft = deepcopy(data)
                draft[group][0]['critChance'] = invalid
                with self.subTest(group=group, invalid=invalid), self.assertRaises(ValueError):
                    b.validate(draft)
            draft = deepcopy(data)
            del draft[group][0]['critChance']
            with self.assertRaises(ValueError):
                b.validate(draft)
            draft = deepcopy(data)
            draft[group][0]['critChance'] = 12.5
            self.assertIn('["critChance"] = 12.5,', b.render(draft))
        for key, values in (('critChance', (-1, 51)), ('maxCritChance', (0, 51)), ('critMultiplier', (0, 5.01))):
            for value in values:
                draft = deepcopy(data); draft['rules'][key] = value
                with self.assertRaises(ValueError): b.validate(draft)
        self.assertEqual(b.OUTPUT.read_text(encoding='utf8'), b.render(data))

    def test_seed_math(self):
        # Design cases, not assertions that prevent editing live values.
        def chance(base, percent=0, flat=0):
            return max(0, min(50, base * (1 + percent/100) + flat))
        for base, percent, flat, expected in ((8, 50, 3, 15), (12, 50, 3, 21), (12, 200, 20, 50), (1, 0, 0, 1), (8, -200, 0, 0)):
            self.assertAlmostEqual(chance(base, percent, flat), expected)
        damage = 80
        self.assertEqual([damage, damage * 1.5, damage * 2, damage * 1.5 * 2], [80, 120, 160, 240])
        for damage, speed, crit, expected in ((70,206,12,53.83),(80,180,8,51.84),(97,154,8,53.78),(104,139,12,53.97)):
            self.assertAlmostEqual(damage*speed/300*(1+crit/100), expected, places=2)

    def test_single_server_critical_path(self):
        stats = read('src/server/character/CharacterStatsService.luau')
        equip = read('src/server/weapon/WeaponEquipService.luau')
        damage = read('src/server/combat/DamageService.luau')
        self.assertIn('CritChance = stats.critChance - Balance.Rules.critChance', equip)
        self.assertIn('CharacterStatsService.ApplyModifiers(character, {})', equip)
        self.assertIn('resolved = Critical.Chance(resolved, percent, flat)', stats)
        self.assertIn('setBase(character, "CritMultiplier", Balance.Rules.critMultiplier)', stats)
        self.assertIn('Critical.Chance(tonumber(attacker:GetAttribute("CritChance")) or 0)', damage)
        self.assertIn('Critical.Multiplier(attacker:GetAttribute("CritMultiplier"))', damage)
        self.assertIn('if balance then balance.critChance else finite(stats.CritChance, 0)', read('src/server/monster/MonsterInitialAttributes.luau'))
        for file in ('AttackDamageResolver', 'BowHitscanService'):
            text = read(f'src/server/combat/{file}.luau')
            self.assertIn('DamageService.Apply(character,', text)
            self.assertIn('HeadshotDamageMultiplier', text)
        self.assertIn('Balance.Rules.maxCritChance', read('src/shared/balance/CriticalStats.luau'))

    def test_gp_validation_lifetime_and_editor(self):
        loadout = read('src/server/dev/GameplayTestLoadout.luau')
        self.assertIn('Critical.ValidateTest(critPercent, critFlat, critMultiplier)', loadout)
        self.assertIn('Stats.SetModifierSource(character, "gameplay-test-critical",', loadout)
        self.assertIn('CritChancePercent=selection.critPercent', loadout)
        self.assertIn('CritChanceFlat=selection.critFlat', loadout)
        self.assertIn('CritMultiplier=selection.critMultiplier - Balance.Rules.critMultiplier', loadout)
        service = read('src/server/dev/GameplayTestService.luau')
        self.assertIn('RunService:IsStudio() and Access.ServerAllowed(player)', service)
        self.assertIn('CharacterService.Respawn(s.player, s.archetype, s.normalFrame)', service)
        ui = read('src/client/dev/GameplayTestController.luau')
        for key in ('Crit buff · %','Crit bonus · pp','Crit damage · ×','Effective crit','critPercent=critPercent,critFlat=critFlat,critMultiplier=critMultiplier'):
            self.assertIn(key, ui)
        self.assertIn("'damage','critChance','xp','gold'", read('system/control-center/static/game-balance.js'))
        self.assertTrue(any(row['patch']==524 for row in logs.load()['entries']))


if __name__ == '__main__': unittest.main()
