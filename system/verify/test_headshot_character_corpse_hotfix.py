"""Contract checks for headshot feedback and no-sink player DeathIdle hotfix."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class HeadshotCharacterDeathHotfixTest(unittest.TestCase):
    def test_headshot_uses_per_hit_server_feedback_not_async_target_attributes(self):
        resolver = read("src/server/combat/AttackDamageResolver.luau")
        damage = read("src/server/combat/DamageService.luau")
        feedback = read("src/server/combat/CombatFeedbackService.luau")
        self.assertIn("DamageService.Apply(character, model, rawDamage, isHeadshot)", resolver)
        self.assertIn("headshot: boolean?", damage)
        self.assertIn("PublishDamage(attacker, target, finalDamage, critical, headshot == true)", damage)
        self.assertIn("headshot = headshot == true", feedback)
        self.assertIn('incoming.relation = "incoming"', feedback)
        self.assertIn('outgoing.relation = "outgoing"', feedback)

    def test_headshot_and_critical_labels_are_independent(self):
        controller = read("src/client/combat/CombatFeedbackController.luau")
        floating = read("src/client/combat/CombatFloatingText.luau")
        self.assertIn("if payload.headshot == true then", controller)
        self.assertIn("CombatFloatingText.ShowHeadshot(payload.target, position)", controller)
        self.assertIn("if critical then", controller)
        self.assertIn("CombatFloatingText.ShowCritical(payload.target, position)", controller)
        self.assertIn('gui.Name = "HeadshotBillboard"', floating)
        self.assertIn('label.Text = "Headshot!"', floating)
        self.assertIn("HEADSHOT_ABOVE_TARGET_STUDS = 4.0", floating)

    def test_only_player_death_disables_sink_monster_still_sinks(self):
        lifecycle = read("src/server/combat/DeathLifecycleService.luau")
        character = read("src/server/character/CharacterService.luau")
        monster = read("src/server/monster/MonsterDeathLifecycle.luau")
        dummy = read("src/server/dev/TrainingDummyService.luau")
        self.assertIn("if options and options.sink == false then", lifecycle)
        self.assertIn("task.delay(Config.DeathIdleSeconds", lifecycle)
        self.assertIn("task.delay(Config.DeathIdleSurfaceSeconds", lifecycle)
        self.assertIn("TweenService:Create(", lifecycle)
        self.assertIn("end, { sink = false })", character)
        self.assertIn('ReturnToTownAvailable", true', character)
        self.assertNotIn("{ sink = false }", monster)
        self.assertNotIn("{ sink = false }", dummy)


if __name__ == "__main__":
    unittest.main()
