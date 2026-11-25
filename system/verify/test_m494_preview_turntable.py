"""M494 local preview rotation integration contracts. See Studio smoke for engine checks."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def source(name):
    return (ROOT / 'src/client/character' / (name + '.luau')).read_text(encoding='utf8')


class PreviewTurntableM494(unittest.TestCase):
    def test_input_capture_only_on_preview_and_not_ui(self):
        code = source('CharacterPreviewTurntable')
        self.assertIn('Enum.UserInputType.MouseButton1 and kind ~= Enum.UserInputType.Touch', code)
        self.assertIn('if input ~= drag then return end', code)
        self.assertIn('UiInputGuard.IsPointerOverUi(input)', code)
        self.assertIn('local id = pick(models, position)', code)
        self.assertIn('part.LocalTransparencyModifier < 0.99', code)
        self.assertIn('Turntable.HitDistance(part, ray)', code)
        self.assertNotIn('CanQuery = true', code)
        self.assertNotIn('BlocksWorldInput', code)  # scene suspension is intentional

    def test_rotation_is_bounded_horizontal_and_local(self):
        code = source('CharacterPreviewTurntable')
        self.assertIn('CFrame.new(base.Position) * CFrame.Angles(0, angle, 0) * base.Rotation', code)
        self.assertIn('1 - math.exp(-RESPONSE * dt)', code)
        self.assertIn('-MAX_SPEED * dt, MAX_SPEED * dt', code)
        self.assertIn('-MAX_PENDING, MAX_PENDING', code)
        self.assertIn('Mounts.UpdateCharacter(model)', code)
        self.assertNotIn('camera.CFrame =', code)
        self.assertNotIn('InvokeServer', code)

    def test_replacement_keeps_angle_and_teardown_disconnects(self):
        code = source('CharacterCreationPreviewController')
        self.assertLess(code.index('self.turntable:Place(archetype, instance, target)'),
                        code.index('self.models[archetype] = instance'))
        self.assertLess(code.index('self.turntable:Place(archetype, instance, target)'),
                        code.index('for part, transparency in pairs(visibility)'))
        self.assertIn('self.turntable:Remove(id)', code)
        self.assertIn('self.turntable:Destroy()', code)
        turn = source('CharacterPreviewTurntable')
        self.assertIn('model:PivotTo(pose(base, rotation.angle))', turn)
        self.assertIn('connection:Disconnect()', turn)
        self.assertIn('WindowFocusReleased', turn)

    def test_scene_gate_and_transparent_curtain(self):
        code = source('CharacterCreationController')
        self.assertIn('curtain:SetAttribute("WorldInputPassthrough", true)', code)
        self.assertIn('curtain.Active = opaque', code)
        self.assertIn('gui.Enabled and sceneReady and not pending and not leaving and not submitting', code)
        self.assertIn('not controls.overlay.Visible and not palette.root.Visible', code)
        self.assertIn('and next(bootstrapPending) == nil', code)
        self.assertIn('if stage == "creation" or stage == "selection" then\n                currentPreview = Preview.new', code)


if __name__ == '__main__':
    unittest.main()
