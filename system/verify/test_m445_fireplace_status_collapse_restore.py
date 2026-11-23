"""M445 regression retained: M446 centralizes minimize/restore in shared dock."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def read(relative):
    return (ROOT / relative).read_text(encoding='utf-8')


class FireplaceStatusCollapseRestoreM445(unittest.TestCase):
    def setUp(self):
        self.ui = read('src/client/world/HouseFireplaceController.luau')
        self.dock = read('src/client/world/InformativeWindowDock.luau')

    def test_one_neutral_pair_of_controls_for_all_informative_views(self):
        self.assertIn('function Dock.Get()', self.dock)
        self.assertIn('function host:Pane(provider: string)', self.dock)
        self.assertIn('collapse.Name = "Collapse"', self.dock)
        self.assertIn('restore.Name = "Restore"', self.dock)
        self.assertIn('chevron(collapse, false, 9)', self.dock)
        self.assertIn('chevron(restore, true, 53)', self.dock)
        self.assertIn('restore.Text = "Инфо"', self.dock)
        self.assertNotIn('restore.Text = "🔥"', self.dock)
        self.assertNotIn('collapse.Text = "✓"', self.dock)

    def test_visibility_has_single_owner_and_source_is_recoverable(self):
        self.assertIn('collapsed[currentSource] = true', self.dock)
        self.assertIn('collapsed[currentSource] = nil', self.dock)
        self.assertIn('panel.Visible = show and not isCollapsed', self.dock)
        self.assertIn('restore.Visible = show and isCollapsed', self.dock)
        self.assertIn('dock:Present("fireplace", socket,', self.ui)
        self.assertNotIn('panel.Visible =', self.ui)
        self.assertNotIn('restore.Visible =', self.ui)
        self.assertIn('dock:Forget(socket)', self.ui)
        self.assertIn('dock:Present("fireplace", nil, "", false)', self.ui)

    def test_idle_registered_source_is_visible_in_range(self):
        self.assertIn('Game1FireplaceFuelState', self.ui)
        self.assertIn('elseif registered(socket) and ray and hoverRadius > 0 then', self.ui)
        self.assertIn('setBar(fuelRow, 0, "Не горит"', self.ui)
        self.assertIn('dock:Present("fireplace", socket,', self.ui)

    def test_button_beside_attack_uses_same_ui_offsets(self):
        self.assertIn('MobileLayout.Resolve(width, height)', self.dock)
        self.assertIn('attack.x + attack.size + bounds.gap', self.dock)
        self.assertNotIn('bounds.attack.gap', self.dock)
        self.assertIn('cfg.offsetXPx', self.dock)
        self.assertIn('cfg.offsetYPx', self.dock)
        self.assertIn('UiSettings.Changed:Connect(applyStyle)', self.dock)
        self.assertIn('UiSettings.Changed:Connect(applyStyle)', self.ui)
        self.assertNotIn('Instance.new("BillboardGui")', self.ui)

    def test_documentation_describes_shared_window(self):
        house = read('system/control-center/mechanics/house.py')
        guide = read('docs/workflows/UI_PRESENTATION_OPTIONS_M443_RU.md')
        self.assertIn('общий контейнер', house.lower())
        self.assertIn('M446', guide)


if __name__ == '__main__':
    unittest.main()
