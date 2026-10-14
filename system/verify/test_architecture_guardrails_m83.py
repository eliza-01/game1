"""M83 architecture guardrails (small source-level tests, not Studio behavioral tests)."""
from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[2]


class ArchitectureGuardrailsM83(unittest.TestCase):
    def test_rojo_directories_are_separate(self):
        tree = json.loads((ROOT / 'default.project.json').read_text(encoding='utf-8'))['tree']
        self.assertEqual(tree['ReplicatedStorage']['Game1Shared']['$path'], 'src/shared')
        self.assertEqual(tree['ServerScriptService']['Game1Server']['$path'], 'src/server')
        self.assertEqual(tree['StarterPlayer']['StarterPlayerScripts']['Game1Client']['$path'], 'src/client')

    def test_shared_contracts_do_not_import_private_server_or_client(self):
        for file in (ROOT / 'src/shared').rglob('*.luau'):
            content = file.read_text(encoding='utf-8')
            with self.subTest(file=str(file.relative_to(ROOT))):
                self.assertNotIn('ServerScriptService', content)
                self.assertNotIn('StarterPlayerScripts', content)
                self.assertNotIn('Players.LocalPlayer', content)

    def test_debug_mutations_are_studio_only(self):
        for filename in ('MovementDebugService.luau', 'MonsterDebugService.luau',
                         'CustomScalingDebugService.luau', 'TestLoadoutService.luau'):
            content = (ROOT / 'src/server/dev' / filename).read_text(encoding='utf-8')
            with self.subTest(filename=filename):
                self.assertIn('RunService:IsStudio()', content)
                self.assertIn('function ', content)

    def test_plugin_source_matches_approved_control_center_button_removal(self):
        content = (ROOT / 'system/studio-plugin/Game1Bridge.server.luau').read_text(encoding='utf-8')
        self.assertIn('local function checkAgent()', content)  # requested legacy preserved
        self.assertNotIn('"Game1ControlCenter"', content)
        self.assertNotIn('button.Click:Connect(checkAgent)', content)

    def test_engineering_rules_and_audit_are_present(self):
        self.assertTrue((ROOT / 'AGENTS.md').is_file())
        self.assertTrue((ROOT / 'docs/ARCHITECTURE_AUDIT_2026-10-14_RU.md').is_file())


if __name__ == '__main__':
    unittest.main()
