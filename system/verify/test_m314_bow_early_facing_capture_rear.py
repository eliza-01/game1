"""M314 narrow bow regressions: Draw facing, late capture, rear contact.

Numerical contact samples model the shared symmetric box/ellipsoid math; the
Luau runtime still requires Studio Play to validate actual rigs and networking.
"""
from pathlib import Path
import math
import unittest

ROOT = Path(__file__).resolve().parents[2]

def src(path):
    return (ROOT / path).read_text(encoding='utf-8')


def ray_box(start_z, dir_z, half_depth):
    lo, hi = (-half_depth - start_z) / dir_z, (half_depth - start_z) / dir_z
    return max(0, min(lo, hi)) if max(0, min(lo, hi)) <= max(lo, hi) else None


class BowDrawFacing(unittest.TestCase):
    def test_draw_turns_before_capture_without_per_frame_target_scan(self):
        attack=src('src/client/combat/AttackController.luau')
        self.assertLess(attack.index('movementController.BeginAimFacingCompensation('),attack.index('bowAimRemote:FireServer({'))
        self.assertIn('bowAimOrigin + bowAimDirection.Unit * AttackConfig.MaxAimDistance',attack)
        self.assertIn('aimPoseController.BeginAttack(presentationTarget, attackDuration)',attack)
        self.assertNotIn('aimPoseController.UpdateTarget(point)',attack)
        self.assertEqual(attack.count('bowAimRemote:FireServer({'),1)
        render=attack.split('RunService.RenderStepped:Connect(function(deltaTime)',1)[1].split('local function attemptAttack()',1)[0]
        self.assertNotIn('GetAimPosition',render)
        self.assertNotIn('bowAimRemote',render)

    def test_100ms_capture_does_not_shorten_server_window(self):
        cfg = src('src/shared/combat/BowProjectileConfig.luau')
        self.assertIn('CaptureLeadSeconds = 0.10', cfg)
        self.assertIn('CaptureWindowSeconds = 0.50', cfg)
        attack = src('src/server/combat/AttackService.luau')
        self.assertIn('finishBowRelease(player, pending)', attack)
        self.assertIn('capture_timeout', attack)


class RearCollisionRegression(unittest.TestCase):
    def test_near_and_far_box_faces_are_direction_symmetric(self):
        for half_depth in (0.2, 0.6, 1.0):
            front = ray_box(2, -1, half_depth)
            rear = ray_box(-2, 1, half_depth)
            self.assertIsNotNone(front)
            self.assertAlmostEqual(front, rear)

    def test_terminal_sweep_extends_only_captured_actor_and_respects_range(self):
        policy=src('src/shared/combat/BowProjectileConfig.luau')
        server=src('src/server/combat/BowHitscanService.luau')
        self.assertIn('OcclusionTolerance = 0.08',policy)
        self.assertIn('withinRange = Range.Within(root.Position, snapshot.point, bowRange)',server)
        self.assertIn('endPoint = from + delta.Unit * math.min(delta.Magnitude, bowRange)',server)
        self.assertNotIn('CapturedActorTerminalMargin',policy)
        self.assertNotIn('CapturedWorldTerminalMargin',policy)

    def test_no_target_magnet_and_melee_unchanged(self):
        server=src('src/server/combat/BowHitscanService.luau')
        melee=src('src/server/combat/AttackService.luau')
        self.assertIn('EntityHitboxService.RaycastAimRegions(character',server)
        self.assertIn('localContact = if part',server)
        self.assertIn('DamageService.Apply(character, target',server)
        self.assertNotIn('capturedEntity:PivotTo',server)
        self.assertIn('if isBow then nil else CharacterAttackWindow.Resolve(timing)',melee)
        self.assertIn('applyDamageInVolume(',melee)
        self.assertNotIn('RunService.Heartbeat:Connect',server)

if __name__ == '__main__':
    unittest.main()
