"""M315: deterministic one-shot capture timing and robust terminal world sweep.

Pure clock scenarios cover capture ordering. Source checks additionally ensure
that the server implements the same state transitions without a stale fallback.
Studio Play remains necessary to validate actual networking and collision.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def simulate_capture(release_at, capture_at, grace=0.2, window=0.5):
    """Expected one-shot server behavior, independent of runtime scheduling."""
    if capture_at is None:
        return "timeout"
    if capture_at < release_at - window:
        return "too_early"
    if capture_at > release_at + grace:
        return "timeout"
    return "on_time" if capture_at <= release_at else "late"


def swept_limit(point_distance, range_limit, actor=False, world=False):
    margin = 0.35 if actor else 0.2 if world else 0
    return min(point_distance + margin, range_limit)


class CaptureNetworkTiming(unittest.TestCase):
    def test_100ms_capture_on_time_late_and_missing(self):
        release = 4.0
        self.assertEqual(simulate_capture(release, 3.90), "on_time")
        self.assertEqual(simulate_capture(release, 4.07), "late")
        self.assertEqual(simulate_capture(release, 4.19), "late")
        self.assertEqual(simulate_capture(release, 4.22), "timeout")
        self.assertEqual(simulate_capture(release, None), "timeout")
        self.assertEqual(simulate_capture(release, 3.0), "too_early")

    def test_single_snapshot_never_substitutes_earlier_aim(self):
        server = read('src/server/combat/AttackService.luau')
        self.assertIn('pending.releaseReached = true', server)
        self.assertIn('pending.captureReceivedAt = now', server)
        self.assertIn('if pending.releaseReached then\n        finishBowRelease(player, pending)', server)
        self.assertIn('CaptureGraceSeconds', server)
        self.assertIn('pending.snapshot = BowHitscanService.Capture(', server)
        self.assertIn('capture_timeout', server)
        self.assertNotIn('pending.snapshot or BowHitscanService.Capture(', server)
        self.assertNotIn('pending.aimOrigin', server)
        self.assertNotIn('pending.aimDirection', server)
        self.assertEqual(server.count('BowHitscanService.Release(player, character, pending.snapshot)'), 1)
        self.assertIn('pendingBowReleases[player] = nil -- consume once', server)
        self.assertIn('if pendingBowReleases[player] ~= pending then return end', server)

    def test_one_client_capture_and_melee_contract_untouched(self):
        client = read('src/client/combat/AttackController.luau')
        self.assertEqual(client.count('bowAimRemote:FireServer({'), 1)
        self.assertIn('CaptureLeadSeconds', client)
        server = read('src/server/combat/AttackService.luau')
        self.assertIn('CharacterAttackWindow.Resolve(timing)', server)
        self.assertIn('applyDamageInVolume(', server)
        self.assertIn('WeaponAttackVolume.Build(', server)


class WorldEndpointCollision(unittest.TestCase):
    def test_world_contact_not_cut_off_at_surface(self):
        for distance in (1.0, 3.4, 30.0):
            self.assertAlmostEqual(swept_limit(distance, 100, world=True), distance + 0.2)
            self.assertAlmostEqual(swept_limit(distance, 100, actor=True), distance + 0.35)
            self.assertEqual(swept_limit(distance, 100), distance)

    def test_max_range_clamps_even_extended_sweep(self):
        for distance, max_range in ((3.0, 3.05), (10.0, 9.0), (40.0, 40.0)):
            self.assertLessEqual(swept_limit(distance, max_range, world=True), max_range)
            self.assertLessEqual(swept_limit(distance, max_range, actor=True), max_range)

    def test_actual_contact_required_before_sticking_or_damage(self):
        hitscan=read('src/server/combat/BowHitscanService.luau')
        visual=read('src/client/combat/BowShotVisualController.luau')
        self.assertIn('local actor = EntityHitboxService.RaycastAimRegions(',hitscan)
        self.assertIn('localContact = if part',hitscan)
        self.assertIn('if not part or not part:IsA("BasePart") or not part.Parent', visual)
        self.assertIn('or typeof(localContact) ~= "Vector3" then', visual)
        self.assertIn('visual:Destroy()',visual)
        self.assertNotIn('RunService.Heartbeat:Connect',hitscan)
        self.assertIn('DamageService.Apply(character, target',hitscan)

if __name__ == '__main__':
    unittest.main()
