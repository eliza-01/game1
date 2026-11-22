"""M446: prevent the M445 nil-layout crash and isolate optional HUD startup.

The missing field in MobileLayout.Resolve was exercised at client Start, before
Studio debug UI. Assert the actual module contract, not a copy of its values.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]

def read(relative):
    return (ROOT / relative).read_text(encoding='utf-8')

class SharedInformativeDockM446(unittest.TestCase):
    def test_restore_placement_reads_real_mobile_layout_contract(self):
        layout = read('src/client/character/mobile/MobileLayout.luau')
        dock = read('src/client/world/InformativeWindowDock.luau')
        self.assertRegex(layout, r'\bgap\s*=\s*math\.floor\(')
        self.assertIn('gap = gap,', layout)
        self.assertIn('attack = {size = attack, x = margin + secondary + gap, y = margin + gap}', layout)
        self.assertIn('local bounds = MobileLayout.Resolve(width, height)', dock)
        self.assertIn('attack.x + attack.size + bounds.gap', dock)
        self.assertNotIn('bounds.attack.gap', dock)
        self.assertNotRegex(dock, r'(?m)^\s*local rightInset\s*=.*attack\.gap')
        self.assertRegex(dock, r'local attack = bounds\.attack\s+local rightInset =')
        self.assertRegex(dock, r'restore\.Position = UDim2\.new\(1,\s+-rightInset \+ cfg\.offsetXPx,')

    def test_shared_chevron_controls_reuse_one_surface(self):
        dock = read('src/client/world/InformativeWindowDock.luau')
        presenter = read('src/client/world/HouseFireplaceController.luau')
        self.assertIn('function Dock.Get()', dock)
        self.assertIn('function host:Pane(provider: string)', dock)
        self.assertIn('function host:Present(provider: string, source: Instance?', dock)
        self.assertIn('function host:Forget(source: Instance)', dock)
        self.assertIn('chevron(collapse, false, 9)', dock)
        self.assertIn('chevron(restore, true, 53)', dock)
        self.assertIn('restore.Text = "Инфо"', dock)
        self.assertNotIn('restore.Text = "🔥"', dock)
        self.assertNotIn('collapse.Text = "✓"', dock)
        self.assertIn('InfoDock.Get()', presenter)
        self.assertIn('dock:Pane("fireplace")', presenter)
        self.assertNotIn('Instance.new("ScreenGui")', presenter)
        self.assertNotIn('panel.Visible', presenter)

    def test_debug_bootstrap_survives_fireplace_presentation_exception(self):
        client = read('src/client/init.client.luau')
        self.assertRegex(client, r'local fireplaceOk, fireplaceError = pcall\(function\(\)')
        self.assertIn('HouseFireplaceController", 5)).Start()', client)
        self.assertRegex(client, r'if not fireplaceOk then\s+warn\(')
        after = client.index('if not fireplaceOk then')
        for name in ('HouseSocketDebugController.Start()',
                     'UiPresentationDebugController', 'TestLoadoutController.Start()',
                     'MovementDebugController.Start()', 'MonsterDebugController.Start()'):
            self.assertIn(name, client[after:])
        self.assertLess(client.index('if not fireplaceOk then'), client.index('HouseSocketDebugController.Start()'))

    def test_status_is_displayed_when_heat_is_off_and_unminimizes(self):
        presenter = read('src/client/world/HouseFireplaceController.luau')
        dock = read('src/client/world/InformativeWindowDock.luau')
        self.assertIn('setBar(fuelRow, 0, "Не горит"', presenter)
        self.assertIn('registered(socket) and distance < minDistance', presenter)
        self.assertIn('dock:Present("fireplace", socket,', presenter)
        self.assertIn('collapsed[currentSource] = nil', dock)
        self.assertIn('collapsed[source] = nil', dock)
        self.assertIn('panel.Visible = show and not isCollapsed', dock)
        self.assertIn('restore.Visible = show and isCollapsed', dock)

if __name__ == '__main__':
    unittest.main()
