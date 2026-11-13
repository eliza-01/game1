"""M323: empty swings silent; server-only aim/pursuit outcome; per-weapon Far cadence."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]

def source(path):
    return (ROOT / path).read_text(encoding="utf-8")


def feedback(pursued, aimed_state, dealt_damage, bow, last_far, now):
    """M324: melee Miss is aimed-ray-only; bow keeps pursuit fallback."""
    if dealt_damage:
        return None, last_far
    if aimed_state == "out_of_range_monster":
        if not bow and last_far is not None and now - last_far < 10:
            return None, last_far
        return "far", last_far if bow else now
    if aimed_state == "in_range" or (bow and pursued):
        return "miss", last_far
    return None, last_far


class OutcomePolicyTests(unittest.TestCase):
    def test_empty_swings_never_show_miss(self):
        for is_bow in (False, True):
            self.assertEqual(feedback(False, None, False, is_bow, None, 1)[0], None)
            self.assertEqual(feedback(False, None, True, is_bow, None, 1)[0], None)

    def test_melee_miss_requires_aimed_target_and_zero_total_damage(self):
        self.assertIsNone(feedback(True, None, False, False, None, 1)[0])
        self.assertEqual(feedback(True, None, False, True, None, 1)[0], "miss")
        for is_bow in (False, True):
            self.assertEqual(feedback(False, "in_range", False, is_bow, None, 1)[0], "miss")
            self.assertIsNone(feedback(True, "in_range", True, is_bow, None, 1)[0])

    def test_far_takes_priority_and_melee_cooldown_is_ten_seconds(self):
        last = None
        emitted = []
        for now in (5, 5.1, 13.5, 14.999, 15, 15.5, 25):
            kind, last = feedback(True, "out_of_range_monster", False, False, last, now)
            if kind:
                emitted.append(now)
        self.assertEqual(emitted, [5, 15, 25])

    def test_bow_reports_far_each_release(self):
        for now in (0.1, 0.7, 1.4):
            self.assertEqual(feedback(False, "out_of_range_monster", False, True, None, now)[0], "far")
        self.assertIsNone(feedback(False, "out_of_range_monster", True, True, None, 1.4)[0])


class IntegrationContracts(unittest.TestCase):
    def test_pure_policy_and_server_ownership(self):
        policy = source("src/shared/combat/AttackFeedbackPolicy.luau")
        service = source("src/server/combat/CombatFeedbackService.luau")
        resolver = source("src/server/combat/AttackFeedbackTargeting.luau")
        self.assertIn('aimedState == "out_of_range_monster"', policy)
        self.assertIn('if aimedState == "in_range" or (isBow and pursued) then', policy)
        self.assertIn('MeleeFarCooldownSeconds = 10', policy)
        self.assertIn('not Policy.CanShowMeleeFar(lastMeleeFar[player], now)', service)
        self.assertIn('HostilePursuitRegistry.IsPursued(character)', service)
        self.assertIn('remote:FireClient(player, {', service)
        self.assertIn('EntityHitboxService.RaycastAimRegions(', resolver)
        self.assertIn('not unobstructed(character, candidate.model, origin, candidate.hitPosition)', resolver)
        self.assertIn('Game1MonsterRuntime', resolver)
        self.assertIn('BowRange.Within(', resolver)
        self.assertIn('Aim.HitWithinAttackRadius(', resolver)
        self.assertNotIn('DamageService.Apply(', resolver)

    def test_one_authoritative_outcome_per_attack_without_extra_remotes(self):
        server = source("src/server/combat/AttackService.luau")
        store = source("src/server/combat/AttackSessionStore.luau")
        client = source("src/client/combat/AttackController.luau")
        ui = source("src/client/combat/CombatFeedbackController.luau")
        text = source("src/client/combat/CombatFloatingText.luau")
        self.assertIn('if reportMiss and not finished.damageDealt', server)
        self.assertIn('if released and damageDealt <= 0', server)
        self.assertEqual(server.count('CombatFeedbackService.PublishAttackOutcome('), 2)
        self.assertIn('AttackSessionStore.SetAim(', server)
        self.assertIn('function AttackSessionStore.SetAim(', store)
        self.assertIn('aimOrigin = meleeAimOrigin', client)
        self.assertIn('payload.kind == "miss" or payload.kind == "far"', ui)
        self.assertIn('CombatFloatingText.ShowFar(', ui)
        self.assertIn('function CombatFloatingText.ShowFar(', text)
        self.assertNotIn('CombatFeedbackService.PublishMissOverPlayer(character)', server)

    def test_incoming_miss_requires_current_pursuit(self):
        service = source("src/server/combat/CombatFeedbackService.luau")
        self.assertIn('if character and HostilePursuitRegistry.IsPursued(character)', service)
        self.assertIn('Policy.AllowIncomingMiss(', service)
        self.assertIn('publishLabel(character, "miss")', service)
        for path in ("src/server/monster/MonsterAttackExecutor.luau", "src/server/npc/NpcCombatAIService.luau"):
            self.assertIn('CombatFeedbackService.PublishMissOverPlayer(target)', source(path))
