"""M488 regression: eye lock UX and pivot-mounted padlock visuals."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]

def source(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf8')

class EyeLockPadlockPivotM488(unittest.TestCase):
    def test_no_both_characters_button(self):
        panel = source('src/client/character/CharacterCreationPanel.luau')
        controller = source('src/client/character/CharacterCreationController.luau')
        self.assertNotIn('BackToOverview', panel)
        self.assertNotIn('controls.back', controller)
        self.assertNotIn('creation.back', controller)
        self.assertNotIn('creation.back', source('assets/manifests/game-localization.json'))

    def test_eye_lock_sync_is_row_level(self):
        view = source('src/client/character/CharacterCreationAppearanceView.luau')
        controller = source('src/client/character/CharacterCreationController.luau')
        self.assertIn('local function lockButton(', view)
        self.assertIn('button.Name = "SyncLock"', view)
        self.assertIn('button.Text = if locked then "🔒" else "🔓"', view)
        self.assertIn('toggleEyeColorsLocked', view)
        self.assertIn('eyeLocks: {[string]: EyeEdit.State}', controller)
        self.assertIn('EyeEdit.Paint(values.colors.eyes, channel, value, eyeLocks[selected].locked)', controller)
        self.assertIn('EyeEdit.Paint(temporary.eyes, channel, hex, eyeLocks[id].locked)', controller)
        self.assertIn('EyeEdit.Toggle(eyeLocks[selected], values.colors.eyes, side)', controller)

    def test_padlock_visual_uses_pivot_mount(self):
        visuals = source('src/server/world/HousePadlockVisuals.luau')
        mount = source('src/server/world/HouseSocketAssetMount.luau')
        pivot = source('src/shared/rig/PivotSocketMount.luau')
        self.assertIn('pcall(Mount.CloneOnPivot, SLUG, socket)', visuals)
        self.assertNotIn('padlock_01_hole_socket', visuals)
        self.assertIn('function Mount.CloneOnPivot(slug: string, target: Attachment): Model?', mount)
        self.assertIn('PivotSocketMount.Align(model, target, visual)', mount)
        self.assertEqual(mount.count('local AuthoredPropSocketMount = require'), 1)
        self.assertIn('model:PivotTo(delta * model:GetPivot())', pivot)
        self.assertIn('Mount.TargetFrame(target)', pivot)
        self.assertIn('origin:GetPivot()', pivot)

if __name__ == '__main__':
    unittest.main()
