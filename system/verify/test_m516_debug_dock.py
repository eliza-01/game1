"""Shared launcher state, responsive layout and independent Gameplay startup."""
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[2]
DEV = ROOT / 'src/client/dev'

class DebugDock(unittest.TestCase):
    def test_all_eight_launchers_use_shared_state(self):
        dock = (DEV / 'StudioDebugDock.luau').read_text(encoding='utf8')
        self.assertIn('GP = 6', dock)
        self.assertIn('launcher.AutoButtonColor = false', dock)
        self.assertIn('local open = panel.Visible and screen.Enabled', dock)
        self.assertIn('if open then SELECTED else CLOSED', dock)
        self.assertIn('if open then ACCENT else TEXT', dock)
        self.assertIn('panel:GetPropertyChangedSignal("Visible"):Connect(paint)', dock)
        for name in ('TestLoadout','CustomScalingDebug','HouseSocketDebug','CameraDebug','HealthUiDebug','UiPresentationDebug','GameplayTest','GameplayAggro'):
            with self.subTest(name=name):
                source = (DEV / (name + 'Controller.luau')).read_text(encoding='utf8')
                self.assertIn('Dock.Bind(', source)
                self.assertIn('Game1DebugPanelOpen', source)
        cs = (DEV / 'CustomScalingDebugController.luau').read_text(encoding='utf8')
        self.assertNotIn('toggle.BackgroundColor3 = palette.accent', cs)

    def test_gameplay_launcher_does_not_wait_for_rpc(self):
        gp = (DEV / 'GameplayTestController.luau').read_text(encoding='utf8')
        self.assertIn('button(gui, "GP", UDim2.fromOffset(44, 44))', gp)
        self.assertIn('StudioDebugDock.Bind(PANEL_ID, launcher, panel, PANEL_WIDTH, true, PANEL_HEIGHT)', gp)
        self.assertNotIn('WaitForChild("GameplayTest"', gp)
        self.assertIn('remotes:FindFirstChild("GameplayTest")', gp)
        self.assertIn('Gameplay server not ready', gp)
        self.assertIn('RunService:IsStudio()', gp)
        self.assertIn('GP launcher ready', gp)
        init = (ROOT / 'src/client/init.client.luau').read_text(encoding='utf8')
        self.assertLess(init.index('DevRoot:WaitForChild("GameplayTestController", 20)'), init.index('HouseSocketDebugController.Start()'))
        self.assertFalse((DEV / 'MonsterDebugController.luau').exists())

    def test_layout_contract_and_bounds(self):
        dock = (DEV / 'StudioDebugDock.luau').read_text(encoding='utf8')
        self.assertIn('math.floor((width - LEFT - 8 + BUTTON_GAP) / STEP)', dock)
        self.assertIn('slot % count', dock)
        self.assertIn('math.floor(slot / count)', dock)
        self.assertIn('screen:GetPropertyChangedSignal("AbsoluteSize"):Connect(layout)', dock)
        for width in (280, 320, 375, 480, 600, 1024, 1920):
            columns = min(8, max(1, (width - 16 - 8 + 8) // 52))
            points = {(16 + i % columns * 52, 8 + i // columns * 52) for i in range(8)}
            self.assertEqual(len(points), 8)
            self.assertTrue(all(x + 44 <= width - 8 for x, y in points))
            panel_top = 60 + ((8 + columns - 1) // columns - 1) * 52
            self.assertTrue(all(y + 44 < panel_top for x, y in points))

if __name__ == '__main__':
    unittest.main()
