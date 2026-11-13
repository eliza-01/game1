"""M330 camera contracts: direct orbit, touch drag / pinch without right joystick."""
from __future__ import annotations

import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAMERA = (ROOT / "src/client/character/CameraController.luau").read_text(encoding="utf-8")
MOBILE = (ROOT / "src/client/character/MobileInputController.luau").read_text(encoding="utf-8")
CONFIG = (ROOT / "src/shared/character/CharacterConfig.luau").read_text(encoding="utf-8")


class ClassicCameraM330(unittest.TestCase):
    def test_no_inertial_camera_and_reduced_sensitivity(self):
        self.assertIn("CFrame.Angles(0, targetYaw, 0)", CAMERA)
        self.assertIn("CFrame.Angles(targetPitch, 0, 0)", CAMERA)
        self.assertNotIn("renderedYaw", CAMERA)
        self.assertNotIn("renderedPitch", CAMERA)
        self.assertNotIn("CameraRotationResponse", CAMERA + CONFIG)
        self.assertNotIn("CameraTouchRotationSpeed", CAMERA + CONFIG)
        self.assertIn("CameraMouseSensitivity = 0.0024", CONFIG)
        self.assertIn("CameraTouchSensitivity = 0.0024", CONFIG)
        self.assertIn("GetRenderCFrame()", CAMERA)
        self.assertIn("GetMouseDelta()", CAMERA)

    def test_right_joystick_removed_and_left_halved(self):
        self.assertIn('makeStick(gui, "MoveStick")', MOBILE)
        self.assertNotIn('makeStick(gui, "LookStick")', MOBILE)
        self.assertNotIn('right.pad', MOBILE)
        self.assertIn("stickSize = math.floor(math.clamp(short * 0.17, 58, 74))", MOBILE)
        self.assertIn("stick.pad.Visible = false", MOBILE)
        self.assertIn("movementController.SetTouchMovement(left.axis, true)", MOBILE)
        self.assertIn('makeAction(gui, "Jump")', MOBILE)
        self.assertIn('makeAction(gui, "Attack")', MOBILE)

    def test_touch_look_is_delta_based_and_ui_safe(self):
        self.assertIn("UiInputGuard.BlocksWorldInput(input, gameProcessed)", MOBILE)
        self.assertIn("cameraController.RotateTouch(current - previous)", MOBILE)
        self.assertIn("if input == left.input then", MOBILE)
        self.assertIn("if #lookFingers == 1 and not pinchLocked then", MOBILE)
        self.assertIn("table.clear(lookFingers)", MOBILE)
        self.assertIn("table.clear(lookPositions)", MOBILE)
        self.assertIn("WindowFocusReleased:Connect(resetTouch)", MOBILE)
        self.assertIn("function CameraController.RotateTouch(delta: Vector2)", CAMERA)

    def test_two_finger_pinch_is_bounded_and_surviving_drag_is_suppressed(self):
        self.assertIn("if #lookFingers == 2 then", MOBILE)
        self.assertIn("cameraController.PinchZoom(pinchGap, currentGap)", MOBILE)
        self.assertIn("table.remove(lookFingers, index)", MOBILE)
        self.assertIn("pinchGap = gapBetweenLookFingers()", MOBILE)
        self.assertIn("pinchLocked = true", MOBILE)
        self.assertIn("if #lookFingers == 0 then", MOBILE)
        self.assertIn("pinchLocked = false", MOBILE)
        self.assertIn("distance * ratio", CAMERA)
        self.assertIn("math.clamp(previousGap / currentGap, 0.7, 1.4)", CAMERA)
        self.assertIn("CharacterConfig.CameraMinDistance", CAMERA)
        self.assertIn("CharacterConfig.CameraMaxDistance", CAMERA)

        # Two simultaneous fingers pulling apart halve camera distance. The
        # movement thumb is not counted in that gesture.
        def zoom(distance: float, old_gap: float, new_gap: float):
            ratio = max(.7, min(1.4, old_gap / new_gap))
            return max(4, min(18, distance * ratio))

        self.assertAlmostEqual(zoom(10, 100, 120), 8.333333333, places=5)
        self.assertEqual(zoom(4, 100, 200), 4)
        self.assertEqual(zoom(18, 100, 50), 18)
        self.assertGreater(zoom(10, 100, 80), 10)

    def test_aim_and_movement_unchanged(self):
        self.assertIn("function CameraController.GetAimRay", CAMERA)
        self.assertIn("ViewportPointToRay", CAMERA)
        self.assertNotIn("FireServer", MOBILE)
        self.assertNotIn("Humanoid:Move", MOBILE)
        self.assertNotIn("CameraType", MOBILE)


if __name__ == "__main__":
    unittest.main()
