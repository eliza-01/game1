"""M602 source contracts and independent camera-space geometry checks.
ControllerManager physics/animation require Studio Play and a mobile device.
"""
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MOVEMENT = (ROOT / 'src/client/character/MovementController.luau').read_text(encoding='utf-8')


class CameraBackpedal(unittest.TestCase):
    def test_backward_mode_has_no_device_or_attack_gate(self):
        mode = MOVEMENT.split('local function backwardLocomotion(', 1)[1].split('\nend', 1)[0]
        self.assertIn('return axis.Y < -0.001', mode)
        for forbidden in ('touchMovementActive', 'aimFacing', 'root', 'rightMouseDown'):
            self.assertNotIn(forbidden, mode)
        self.assertNotIn('backwardRelativeDirection', MOVEMENT)
        self.assertNotIn('backwardCameraSteering', MOVEMENT)

    def test_only_camera_basis_controls_world_travel(self):
        direction = MOVEMENT.split('local function cameraRelativeDirection(', 1)[1].split('\nend', 1)[0]
        self.assertIn('Workspace.CurrentCamera', direction)
        self.assertIn('forwardFlat * axis.Y + rightFlat * axis.X', direction)
        self.assertNotIn('root', direction)
        update = MOVEMENT.split('local function updateMovement(', 1)[1].split('function MovementController.SetTouchMovement', 1)[0]
        self.assertIn('if backwardActive and not touchMovementActive and not liveAttackAim then\n\t\t\taxis = Vector2.new(0, -1)', update)
        self.assertEqual(update.count('moveDirection = cameraRelativeDirection(axis)'), 1)
        self.assertIn('if not movementLocked then', update)
        self.assertIn('controllerManager.MovingDirection = moveDirection', update)

    def test_facing_and_gait_integration(self):
        self.assertIn('local lowerBodyFacing = if backwardActive then cameraForwardDirection() else moveDirection', MOVEMENT)
        self.assertIn('local cameraForward = cameraForwardDirection()', MOVEMENT)
        self.assertIn('controllerManager.FacingDirection = cameraForward', MOVEMENT)
        self.assertIn('local walkActive = walkModifierActive or backwardActive', MOVEMENT)
        self.assertIn('local nextDirectionMode = backwardActive and "Backward" or "Forward"', MOVEMENT)
        self.assertIn('elseif facingLockDirection and now < facingLockUntil then', MOVEMENT)
        self.assertIn('applyAimFacingCompensation(now, deltaTime, moveDirection.Magnitude > 0.001)', MOVEMENT)
        animation = (ROOT / 'src/client/character/animation/CharacterAnimationController.luau').read_text(encoding='utf-8')
        self.assertIn('AnimationMovementDirection', animation)
        self.assertIn('applyBackwardPlayback', animation)

    def test_camera_yaw_and_analog_geometry(self):
        # Independent reference: yaw can change while input is held, and root yaw
        # is irrelevant. Dot products expose both forward and lateral components.
        for degrees in (0, 45, 90, 180, 270, 359):
            yaw = math.radians(degrees)
            forward = (math.sin(yaw), -math.cos(yaw))
            right = (math.cos(yaw), math.sin(yaw))
            for x, y in ((0, -1), (0, -.3), (.4, -.6), (-.5, -.5), (1, 0), (0, 1), (0, 0)):
                with self.subTest(yaw=degrees, x=x, y=y):
                    world = tuple(f*y+r*x for f, r in zip(forward, right))
                    self.assertAlmostEqual(sum(a*b for a, b in zip(world, forward)), y)
                    self.assertAlmostEqual(sum(a*b for a, b in zip(world, right)), x)
                    self.assertAlmostEqual(math.hypot(*world), math.hypot(x, y))


if __name__ == '__main__':
    unittest.main()
