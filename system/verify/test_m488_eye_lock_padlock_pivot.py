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
        self.assertIn('local function lockHeading(', view)
        self.assertIn('button.Name = "SyncLock"', view)
        self.assertIn('button.Text = if locked then "🔒" else "🔓"', view)
        self.assertIn('toggleEyeColorsLocked', view)
        self.assertIn('eyeLocks: {[string]: boolean}', controller)
        self.assertIn('if group == "eyes" and channel and eyeLocks[selected] then', controller)
        self.assertIn('values.colors[group]["l"] = value', controller)
        self.assertIn('values.colors[group]["r"] = value', controller)
        self.assertIn('if group == "eyes" and eyeLocks[id] then', controller)
        self.assertIn('eyeLocks[selected] = not eyeLocks[selected]', controller)

    def test_padlock_visual_uses_pivot_mount(self):
        visuals = source('src/server/world/HousePadlockVisuals.luau')
        mount = source('src/server/world/HouseSocketAssetMount.luau')
        pivot = source('src/shared/rig/PivotSocketMount.luau')
        self.assertIn('pcall(Mount.CloneOnPivot, SLUG, socket)', visuals)
        self.assertNotIn('padlock_01_hole_socket', visuals)
        self.assertIn('function Mount.CloneOnPivot(slug: string, target: Attachment): Model?', mount)
        self.assertIn('PivotSocketMount.Align(model, target)', mount)
        self.assertEqual(mount.count('local AuthoredPropSocketMount = require'), 1)
        self.assertIn('model:PivotTo(targetFrame)', pivot)
        self.assertIn('SocketFacing.FullFrame', pivot)

if __name__ == '__main__':
    unittest.main()
