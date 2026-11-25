"""M522: compact GP presentation; authoritative loadout and recovery contracts stay intact."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
UI = (ROOT / 'src/client/dev/GameplayTestController.luau').read_text(encoding='utf8')
DOCK = (ROOT / 'src/client/dev/StudioDebugDock.luau').read_text(encoding='utf8')


class CompactGameplay(unittest.TestCase):
    def test_bottom_left_and_order(self):
        self.assertIn('PANEL_WIDTH, PANEL_HEIGHT = 380, 332', UI)
        self.assertIn('UDim2.new(0.5, -3, 1, 0)', UI)
        self.assertIn('panel.AnchorPoint = Vector2.new(0, 1)', DOCK)
        self.assertIn('panel.Position = UDim2.new(0, 8, 1, -8)', DOCK)
        self.assertIn('if adaptive and not bottomHeight then', DOCK)
        items = ['cell(first, "Level")', 'cell(first, "Weapon")', 'cell(second, "Armor")',
                 'cell(second, "Upgrade")', 'cell(third, "Monster")', 'cell(third, "Group")',
                 'cell(recoveryRow, "Regeneration")', 'cell(recoveryRow, "Vampiric")',
                 'local actions = row', 'contentButton(navigation, "Go"']
        self.assertEqual(sorted(UI.index(x) for x in items), [UI.index(x) for x in items])
        self.assertIn('start.Size.X.Offset + 4', UI)
        self.assertIn('TextService:GetTextSize', UI)
        self.assertNotIn('Visit passive monster', UI)
        self.assertNotIn('Apply recovery', UI)

    def test_required_level(self):
        self.assertIn('Balance.Grade.ForLevel(weapon().level)', UI)
        self.assertIn('return math.max(required, armor().level)', UI)
        self.assertIn('level = math.max(level, minimumLevel()); refreshLevel()', UI)
        self.assertIn('math.clamp(level + d, minimumLevel(), #Balance.Monsters)', UI)
        self.assertEqual(UI.count('); ensureLevel()'), 2)
        registry = json.loads((ROOT / 'config/balance/gameplay.json').read_text(encoding='utf8'))
        for w in registry['weapons']:
            for a in registry['armor']:
                required = max(1, (w['level'] // 10) * 10, a['level'])
                self.assertLessEqual(required, len(registry['levels']))
                if w['level'] == 15 and a['level'] == 1:
                    self.assertEqual(required, 10)
                if a['level'] == 35:
                    self.assertEqual(required, 35)

    def test_recovery_and_successful_close(self):
        self.assertIn('local enabled = false', UI)
        self.assertIn('enabled = not enabled', UI)
        self.assertIn('if not enabled then return 0 end', UI)
        self.assertIn('input.FocusLost:Connect', UI)
        self.assertIn('invoke("recovery")', UI)
        self.assertIn('local closeOnSuccess = {enter=true, apply=true, start=true, visit=true, exit=true}', UI)
        self.assertIn('response.ok and closeOnSuccess[action]', UI)
        self.assertIn('if action == "recovery" then queuedRecovery = true else queuedAction = action end', UI)
        self.assertIn('local delaySeconds = 0.4 - (os.clock() - lastRequestAt)', UI)


if __name__ == '__main__':
    unittest.main()
