"""M319: travel drives lower body; live reticle drives the upper-body spine.

Physics/skin pose require Studio; these tests cover deterministic angle policy,
client integration, mobile input, and the server-side yaw envelope.
"""
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def source(path):
    return (ROOT / path).read_text(encoding="utf-8")


def facing_policy(stick, camera_heading=0):
    """2D camera-space analogue of MovementController during a bow action."""
    x, y = stick
    forward = (math.cos(camera_heading), math.sin(camera_heading))
    right = (-math.sin(camera_heading), math.cos(camera_heading))
    move = (forward[0] * y + right[0] * x, forward[1] * y + right[1] * x)
    magnitude = math.hypot(*move)
    if not magnitude:
        return (0, 0), None, "Idle"
    move = tuple(v / max(1, magnitude) for v in move)
    if y < -0.001:
        return move, forward, "Backward"
    return move, tuple(v / magnitude for v in move), "Forward"


def relative_yaw(facing, aim):
    return math.atan2(facing[0]*aim[1] - facing[1]*aim[0],
                      facing[0]*aim[0] + facing[1]*aim[1])


class BowMovementM319(unittest.TestCase):
    def test_camera_relative_travel_and_lower_body_authority(self):
        for stick in ((0, 1), (1, 0), (-1, 0), (.7, .7), (-.7, .7)):
            move, legs, gait = facing_policy(stick)
            self.assertEqual(gait, 'Forward')
            magnitude = math.hypot(*move)
            for actual, expected in zip(legs, (value / magnitude for value in move)):
                self.assertAlmostEqual(actual, expected)
            self.assertLessEqual(abs(math.degrees(relative_yaw(legs, (1, 0)))), 90.01)
        for stick in ((0, -1), (0.5, -0.8), (-0.8, -0.5)):
            move, legs, gait = facing_policy(stick)
            self.assertEqual(gait, 'Backward')
            self.assertEqual(legs, (1, 0))
            self.assertLess(move[0], 0)
            self.assertNotEqual(move, legs)
        for heading in (0, 0.7, -1.9):
            move, legs, gait = facing_policy((1, 0), heading)
            for actual, expected in zip(legs, move):
                self.assertAlmostEqual(actual, expected)
            self.assertEqual(gait, 'Forward')
        self.assertEqual(facing_policy((0, 0))[2], 'Idle')

    def test_upper_body_covers_strafe_without_relaxing_hitscan_validation(self):
        attack = source('src/shared/combat/AttackConfig.luau')
        bow = source('src/shared/combat/BowProjectileConfig.luau')
        self.assertIn('MovingBowTorsoYawLimit = math.rad(100)', attack)
        self.assertIn('TorsoYawLimit = math.rad(70)', attack)
        self.assertIn('MaxAimYaw = math.rad(145)', bow)
        pose = source('src/client/combat/AimPoseController.luau')
        self.assertIn('local yawLimit = if movingBow then AttackConfig.MovingBowTorsoYawLimit else AttackConfig.TorsoYawLimit', pose)
        self.assertIn('pitchRotation * yawRotation * animatedRotation', pose)
        self.assertIn('math.atan2(math.sin(desiredYaw - renderedYaw), math.cos(desiredYaw - renderedYaw))', pose)
        self.assertIn('CharacterUpperBodyRig.ResolveBridge(visual)', pose)
        rig = source('src/client/character/animation/CharacterUpperBodyRig.luau')
        self.assertIn('hasLowerBodyDescendants(candidate)', rig)

    def test_root_transform_is_not_aim_written_while_walking(self):
        movement = source('src/client/character/MovementController.luau')
        self.assertIn('if liveBowAim and moveDirection.Magnitude > 0.001 then', movement)
        self.assertIn('local lowerBodyFacing = if backwardActive then cameraForwardDirection() else moveDirection', movement)
        self.assertIn('controllerManager.FacingDirection = lowerBodyFacing', movement)
        self.assertNotIn('controllerManager.FacingDirection = aimFacingTargetDirection', movement)
        self.assertIn('if moving then return end', movement)
        comp = movement.split('local function applyAimFacingCompensation(', 1)[1].split('local function applyMovementMode(', 1)[0]
        self.assertLess(comp.index('if moving then return end'), comp.index('navigationRoot.CFrame = CFrame.lookAt('))
        self.assertIn('yaw - math.clamp(yaw, -aimFacingMaxResidualYaw, aimFacingMaxResidualYaw)', comp)
        self.assertIn('applyAimFacingCompensation(now, deltaTime, moveDirection.Magnitude > 0.001)', movement)

    def test_no_new_bow_damage_or_camera_writer(self):
        movement = source('src/client/character/MovementController.luau')
        self.assertIn('if liveBowAim then\n\t\t\tmoveDirection = cameraRelativeDirection(axis)', movement)
        self.assertIn('local backwardActive = backwardLocomotion(axis)', movement)
        attack = source('src/client/combat/AttackController.luau')
        self.assertEqual(attack.count('bowAimRemote:FireServer({'), 1)
        self.assertIn('bowPresentationUntil = os.clock() + attackDuration', attack)
        self.assertIn('finishPresentation(bowCaptureSequence)', attack)
        self.assertIn('aimPoseController.UpdateTarget(target)', attack)
        self.assertNotIn('CameraController.SetTouchLookAxis(', movement)


if __name__ == '__main__':
    unittest.main()
