"""M325: close-contact pose uses reticle elevation, never hitbox parallax.

These math examples reproduce the Luau presentation policy; Studio must still
confirm the resulting skinned Bone pose and camera offsets.
"""
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def source(path):
    return (ROOT / path).read_text(encoding="utf-8")

def pitch(ray, displacement, neutral=3.0, full=9.0):
    if not ray or math.sqrt(sum(v*v for v in ray)) <= 1e-6:
        return 0.0
    camera_pitch = math.atan2(ray[1], max(1e-6, math.hypot(ray[0], ray[2])))
    if camera_pitch >= 0:
        return camera_pitch
    target_distance = math.hypot(displacement[0], displacement[2])
    t = max(0, min(1, (target_distance-neutral)/max(.001, full-neutral)))
    return camera_pitch*t*t*(3-2*t)

class CloseRangeAimPitchM325(unittest.TestCase):
    def test_camera_down_hitbox_above_character_does_not_tilt_head_up(self):
        camera_ray = (0, -0.35, -1)
        hit_above_root = (0, 4, -1)
        old_head_pitch = math.atan2(hit_above_root[1], 1)
        self.assertGreater(math.degrees(old_head_pitch), 70)
        self.assertAlmostEqual(pitch(camera_ray, hit_above_root), 0)
        # Target height must never leak into presentation pitch.
        self.assertEqual(pitch(camera_ray, (0, -5, -1)), pitch(camera_ray, hit_above_root))

    def test_near_to_far_downward_aim_is_continuous(self):
        ray = (0, -1, -1)
        values = [pitch(ray, (0, 4, -d)) for d in (1,3,4,6,8,9,15)]
        self.assertAlmostEqual(values[0], 0)
        self.assertAlmostEqual(values[-1], -math.pi/4)
        self.assertTrue(all(a >= b for a,b in zip(values, values[1:])))
        self.assertGreater(values[3], -math.pi/4)

    def test_upward_aim_still_allowed_at_any_distance(self):
        for distance in (0.2, 1, 3, 6, 9, 40):
            self.assertAlmostEqual(pitch((0, 1, -1), (0, 3, -distance)), math.pi/4)
        self.assertEqual(pitch(None, (0, 5, -1)), 0)

    def test_shared_policy_used_only_for_cosmetic_pitch(self):
        pose=source('src/client/combat/AimPoseController.luau')
        attack=source('src/client/combat/AttackController.luau')
        config=source('src/shared/combat/AttackConfig.luau')
        geometry=source('src/shared/combat/AimPitchGeometry.luau')
        self.assertIn('AimPitchGeometry.Resolve(',pose)
        self.assertNotIn('math.atan2(direction.Y',pose)
        self.assertIn('presentationAimDirection = nil',pose)
        self.assertIn('presentationAimDirection = direction.Unit',pose)
        self.assertIn('aimPoseController.UpdateTarget(target, direction)',attack)
        self.assertIn('CloseAimPitchNeutralStuds = 3',config)
        self.assertIn('CloseAimPitchFullStuds = 9',config)
        self.assertIn('return cameraPitch * smooth',geometry)
        self.assertIn('return cameraPitch -- deliberate upward aim',geometry)
        self.assertNotIn('AimPitchGeometry',source('src/server/combat/BowHitscanService.luau'))
        self.assertNotIn('AimPitchGeometry',source('src/server/combat/AttackService.luau'))

if __name__ == '__main__':
    unittest.main()
