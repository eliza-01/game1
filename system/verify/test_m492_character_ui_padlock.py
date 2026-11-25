"""M492 regression contracts. Live asset/bone alignment requires Studio."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def src(path):
    return (ROOT / path).read_text(encoding='utf8')


class CharacterUiPadlockM492(unittest.TestCase):
    def test_lock_next_to_custom_in_same_layout(self):
        view = src('src/client/character/CharacterCreationAppearanceView.luau')
        self.assertNotIn('lockHeading', view)
        self.assertIn('customButton.Parent = actions', view)
        self.assertIn('customButton.LayoutOrder = 1', view)
        self.assertIn('lockButton(actions, 2, eyeLock, toggleEyeLock)', view)
        self.assertIn('button.LayoutOrder = order', view)
        self.assertIn('holder:GetPropertyChangedSignal("AbsoluteSize"):Connect(resize)', view)

    def test_one_animated_loader_and_no_brand(self):
        panel = src('src/client/character/CharacterCreationPanel.luau')
        for removed in ('GameBrand', 'GoldAccent', 'GAME1  /  CHARACTER', '"Sword"'):
            self.assertNotIn(removed, panel)
        self.assertIn('RunService.RenderStepped:Connect(render)', panel)
        self.assertIn('setRunnerPose(views.overlayRunner, elapsed)', panel)
        self.assertIn('views.runnerConnection:Disconnect()', panel)
        self.assertIn('else position * 0.78', panel)
        self.assertIn('if value ~= nil then string.format', panel)
        self.assertEqual(panel.count('local function setOverlay('), 1)
        self.assertIn('setOverlay(views, busy, message, progress)', panel)

    def test_world_entry_waits_for_camera_and_actual_character_preload(self):
        controller = src('src/client/character/CharacterCreationController.luau')
        sync = controller.split('local function sync()')[1]
        camera = sync.index('while epoch == token and not CameraController.ClearCreationView()')
        preload = sync.index('pcall(MeshPreloader.PreloadModel, model, current')
        hide = sync.index('Panel.SetSubmitting(controls, false, "")')
        self.assertLess(camera, preload)
        self.assertLess(preload, hide)
        self.assertIn('worldProgress = nil', sync)
        self.assertIn('worldProgress = progress', sync)
        self.assertIn('player.Character == model', sync)
        self.assertIn('Panel.SetSubmitting(controls, true, Language.Translate("creation.entering_world"), worldProgress)', sync)
        self.assertIn('elseif next(bootstrapPending) then', controller)
        self.assertIn('for id in pairs(bootstrapPending) do partial += bootstrapProgress[id] or 0 end', controller)

    def test_bone_frame_and_visual_origin_without_rebasing_carrier(self):
        mount = src('src/shared/rig/PivotSocketMount.luau')
        adapter = src('src/server/world/HouseSocketAssetMount.luau').split('function Mount.CloneOnPivot(')[1]
        self.assertNotIn('OBJECT_TO_BONE', mount)
        self.assertIn('return (socket :: Bone).TransformedWorldCFrame\n', mount)
        self.assertIn('return socket.WorldCFrame', mount)
        self.assertIn('targetFrame * origin:GetPivot():Inverse()', mount)
        self.assertIn('matches(origin:GetPivot(), targetFrame)', mount)
        self.assertIn('part:IsA("MeshPart") and part.Name == slug', adapter)
        self.assertIn('PivotSocketMount.Align(model, target, visual)', adapter)
        self.assertNotIn('PrimaryPart =', adapter)
        self.assertNotIn('PivotOffset =', mount + adapter)
        self.assertNotIn('GetBoundingBox', mount + adapter)
        self.assertNotIn('Upright', mount)


if __name__ == '__main__':
    unittest.main()
