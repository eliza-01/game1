"""M519: server-owned, transient test-only regeneration and lifesteal."""
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[2]
def read(p): return (ROOT / p).read_text(encoding='utf8')

class TestRecovery(unittest.TestCase):
    def test_default_and_scope(self):
        self.assertIn('RegenerationHPPerSecond = 1', read('src/shared/character/CharacterStatsConfig.luau'))
        healing = read('src/server/character/CharacterHealing.luau')
        for text in ('not RunService:IsStudio()', 'Players:GetPlayerFromCharacter(character)', 'owner.Character ~= character', 'Game1GameplayTestActive', 'Game1GameplayTestOwner', 'kind ~= "zone" and kind ~= "group"', 'amount < math.huge', 'math.min(amount, maxHP - hp)', 'value >= 0 and value <= maximum'):
            self.assertIn(text, healing)
        regen = read('src/server/character/CharacterRegenerationService.luau')
        self.assertIn('if not RunService:IsStudio() and Config.RegenerationHPPerSecond <= 0 then return end', regen)
        self.assertIn('if rate > 0 then Healing.Restore(character, rate * elapsed) end', regen)

    def test_damage_loss_not_overkill(self):
        source = read('src/server/combat/DamageService.luau')
        self.assertIn('Healing.OnDamage(attacker, target, hp - newHP)', source)
        self.assertLess(source.index('target:SetAttribute("HP", newHP)'), source.index('Healing.OnDamage'))
        self.assertIn('actualLoss * rate / 100', read('src/server/character/CharacterHealing.luau'))
        for hp, damage, percent, attacker_hp, maximum, expected in ((20, 100, 25, 40, 100, 45), (100, 40, 50, 90, 100, 100), (100, 0, 100, 40, 100, 40), (100, 40, 0, 40, 100, 40)):
            self.assertEqual(min(maximum, attacker_hp + min(hp, damage)*percent/100), expected)

    def test_live_settings_and_respawn(self):
        loadout = read('src/server/dev/GameplayTestLoadout.luau')
        self.assertIn('Healing.ValidateTestRates(regen, vampiric)', loadout)
        self.assertIn('selection.regen = regen', loadout)
        self.assertIn('selection.vampiric = vampiric', loadout)
        self.assertIn('applyRecovery(character, selection)\n    Stats.SetProgressionLevel', loadout)
        service = read('src/server/dev/GameplayTestService.luau')
        self.assertIn('if action == "recovery" then', service)
        self.assertIn('Loadout.SetRecovery(player, character, request.regen, request.vampiric)', service)
        self.assertNotIn('SetAttribute("HP"', service.split('if action == "recovery" then', 1)[1].split('if action == "stop"', 1)[0])
        ui = read('src/client/dev/GameplayTestController.luau')
        for token in ('Regen · HP/sec', 'Vampiric · %', 'invoke("recovery")', 'regen=regen,vampiric=vampiric', 'input.Text = "0"'):
            self.assertIn(token, ui)
