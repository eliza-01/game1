from pathlib import Path
import json
import tempfile
import shutil
import subprocess
import unittest
from diagnostic_payloads import require_payloads

ROOT = Path(__file__).resolve().parents[2]

class OverheadIntegrationM647(unittest.TestCase):
    def test_payload_skip_requires_exact_omission(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaises(AssertionError):
                require_payloads(self, root, ['asset.png'])
            (root / '_dump').mkdir()
            (root / '_dump/model_files.json').write_text(json.dumps({'files': [{'path': 'asset.png'}]}))
            with self.assertRaises(unittest.SkipTest):
                require_payloads(self, root, ['asset.png'])
            with self.assertRaises(AssertionError):
                require_payloads(self, root, ['asset.png', 'unlisted.png'])
            (root / 'asset.png').write_bytes(b'present')
            require_payloads(self, root, ['asset.png'])

    def test_late_geometry_updates_only_bound_view(self):
        registry = (ROOT/'src/client/combat/MnpcOverheadRegistry.luau').read_text()
        controller = (ROOT/'src/client/combat/MnpcOverheadController.luau').read_text()
        self.assertIn('record.offsetDirty = true', registry)
        self.assertIn('if record.offsetDirty then\n            view.RefreshVisualOffset()\n            record.offsetDirty = nil', controller)
        self.assertIn('record.retryAt, record.waitSince, record.offsetDirty = nil, nil, nil', controller)
        self.assertEqual(controller.count('Heartbeat:Connect'), 1)

    def test_actual_coordinator_integration_with_roblox_doubles(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua:
            self.skipTest('Standalone Lua unavailable')
        source = (ROOT/'src/client/combat/MnpcOverheadController.luau').read_text()
        conversions = {
            'model = if parent and parent:IsA("Model") then parent\n            elseif parent then parent:FindFirstAncestorOfClass("Model") else nil':
                'model = (parent and parent:IsA("Model") and parent) or (parent and parent:FindFirstAncestorOfClass("Model"))',
            'if character then {character} else {}': '(character and {character} or {})',
            'if playerRoot and next(registry.readyMonsters) ~= nil then reticleTarget(radius) else nil':
                '(playerRoot and next(registry.readyMonsters) ~= nil and reticleTarget(radius) or nil)',
            'if character then tonumber(character:GetAttribute("Level")) or 1 else 1':
                '(character and tonumber(character:GetAttribute("Level")) or 1)',
            'if record.kind == "NPC" then math.max(profile.nameRadiusStuds, profile.healthRadiusStuds) + 80 else nil':
                '(record.kind == "NPC" and math.max(profile.nameRadiusStuds, profile.healthRadiusStuds) + 80 or nil)',
            'epoch += 1': 'epoch = epoch + 1',
            'created += 1': 'created = created + 1',
            'elapsed += dt': 'elapsed = elapsed + dt',
        }
        for original, adapted in conversions.items():
            self.assertIn(original, source)
            source = source.replace(original, adapted)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'controller.lua'
            path.write_text(source, encoding='utf-8')
            subprocess.run([lua, str(ROOT/'system/verify/overhead_pool_m646.lua'), str(ROOT), str(path)], check=True, timeout=20)
