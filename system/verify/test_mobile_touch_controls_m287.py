"""M287: integration contracts for the custom touch input adapter.

Roblox touch gestures/ControllerManager physics still require Device Simulator + device.
"""
from __future__ import annotations

import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOUCH = (ROOT / "src/client/character/MobileInputController.luau").read_text(encoding="utf-8")
MOVEMENT = (ROOT / "src/client/character/MovementController.luau").read_text(encoding="utf-8")
CAMERA = (ROOT / "src/client/character/CameraController.luau").read_text(encoding="utf-8")
ATTACK = (ROOT / "src/client/combat/AttackController.luau").read_text(encoding="utf-8")
INIT = (ROOT / "src/client/init.client.luau").read_text(encoding="utf-8")
CONFIG = (ROOT / "src/shared/character/CharacterConfig.luau").read_text(encoding="utf-8")
PROJECT = (ROOT / "default.project.json").read_text(encoding="utf-8")


class MobileTouchControlsM287(unittest.TestCase):
    def test_single_source_of_movement_and_camera_physics(self):
        self.assertIn('"CreateDefaultPlayerModule": false', PROJECT)
        self.assertIn('if started or not UserInputService.TouchEnabled then', TOUCH)
        self.assertIn('movementController.SetTouchMovement(left.axis, true)', TOUCH)
        self.assertIn('cameraController.SetTouchLookAxis(right.axis)', TOUCH)
        self.assertIn('touchMovementActive', MOVEMENT)
        self.assertIn('controllerManager.MovingDirection = moveDirection', MOVEMENT)
        self.assertIn('CameraController.SetTouchLookAxis', CAMERA)
        self.assertIn('CameraTouchRotationSpeed', CAMERA)
        self.assertIn('CameraTouchRotationSpeed = 2.6', CONFIG)
        self.assertNotIn('Humanoid:Move(', TOUCH)
        self.assertNotIn('CameraType', TOUCH)
        self.assertNotIn('FireServer', TOUCH)

    def test_multitouch_and_release(self):
        self.assertIn('UserInputService.TouchStarted:Connect', TOUCH)
        self.assertIn('UserInputService.TouchMoved:Connect', TOUCH)
        self.assertIn('UserInputService.TouchEnded:Connect', TOUCH)
        self.assertIn('input == left.input', TOUCH)
        self.assertIn('input == right.input', TOUCH)
        self.assertIn('UserInputService.WindowFocusReleased:Connect(resetTouch)', TOUCH)
        self.assertIn('movementController.SetTouchMovement(Vector2.zero, false)', TOUCH)
        self.assertIn('cameraController.SetTouchLookAxis(Vector2.zero)', TOUCH)
        self.assertIn('gui.ResetOnSpawn = false', TOUCH)
        self.assertIn('GetPropertyChangedSignal("ViewportSize")', TOUCH)

    def test_touch_backwards_is_camera_relative_not_keyboard_backpedal(self):
        self.assertIn('if touchMovementActive then\n\t\treturn touchAxis', MOVEMENT)
        self.assertIn('not touchMovementActive and isBackwardAxis(axis)', MOVEMENT)
        self.assertIn('backwardActive and backwardRelativeDirection(axis, backwardCameraSteering) or cameraRelativeDirection(axis)', MOVEMENT)

    def test_jump_and_attack_share_desktop_rules(self):
        self.assertIn('MovementController.RequestJump()', MOVEMENT)
        self.assertIn('movementController.RequestJump()', TOUCH)
        self.assertIn('AttackController.RequestAttack = attemptAttack', ATTACK)
        self.assertIn('attackController.RequestAttack()', TOUCH)
        self.assertEqual(ATTACK.count('animationController.PlayAction("attack")'), 1)
        self.assertEqual(ATTACK.count('attack:FireServer({'), 1)
        self.assertIn('and not UiInputGuard.BlocksWorldInput(input, processed)', ATTACK)
        self.assertIn('MobileInputController.Start(MovementController, CameraController, AttackController)', INIT)

    def test_stick_axes_are_bounded_and_analog(self):
        # Reflects MobileInputController.moveStick's deadzone + clipping math.
        def axis(dx: float, dy: float, radius: float = 50.0):
            length = math.hypot(dx, dy)
            clipped = min(length, radius)
            norm = clipped / radius
            strength = max(0.0, min(1.0, (norm - 0.12) / 0.88))
            if not strength:
                return (0.0, 0.0)
            return (dx / length * strength, -dy / length * strength)

        self.assertEqual(axis(0, 0), (0, 0))
        self.assertEqual(axis(5, 0), (0, 0))
        self.assertAlmostEqual(axis(0, -500)[1], 1)
        self.assertAlmostEqual(axis(500, 0)[0], 1)
        self.assertAlmostEqual(math.hypot(*axis(30, 30)), (math.hypot(30, 30) / 50 - 0.12) / .88)
        self.assertIn('local strength = math.clamp((normalized.Magnitude - DEADZONE) / (1 - DEADZONE), 0, 1)', TOUCH)
        self.assertIn('stick.axis = if strength > 0 then', TOUCH)


if __name__ == '__main__':
    unittest.main()
