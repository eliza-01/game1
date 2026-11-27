"""M625 event-driven composite effect lifecycle and integration."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


class CompositeEffectsM625(unittest.TestCase):
    def test_actual_module_signal_oracle(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua:
            self.skipTest('Lua CLI unavailable')
        subprocess.run([lua, 'system/verify/location_composite_effects_m625.lua'],
                       cwd=ROOT, check=True, timeout=30)

    def test_no_periodic_composite_effect_pass(self):
        source = read('src/client/world/LocationWorldStreamer.luau')
        tick = source.split('RunService.Heartbeat:Connect', 1)[1]
        self.assertNotIn('ipairs(composites)', tick)
        self.assertNotIn('compositeVisits', source)
        self.assertNotIn('deferredEffects', source)
        self.assertEqual(source.count('RunService.Heartbeat:Connect'), 1)
        self.assertIn('LocationCompositeEffects.new(Workspace, composites, diagnostics)', source)
        self.assertIn('state.compositeEffects:Destroy()', source)
        self.assertEqual(source.count('compositeEffects:ActualChanged(record)'), 2)
        commit = source.split('function callbacks.commit', 1)[1].split('local function sampleWork', 1)[0]
        self.assertLess(commit.index('record.actual ='), commit.index('compositeEffects:ActualChanged(record)'))
        self.assertIn('record.actual = "UNLOADED"\n                if record.components then compositeEffects:ActualChanged(record) end', tick)
        self.assertNotIn('SetEffects', read('src/client/world/LocationCompositeVisual.luau'))

    def test_scoped_events_and_diagnostics(self):
        effects = read('src/client/world/LocationCompositeEffects.luau')
        diagnostics = read('src/client/world/LodDiagnostics.luau')
        for token in ('ChildAdded:Connect', 'ChildRemoved:Connect', 'DescendantAdded:Connect',
                      'DescendantRemoving:Connect', 'GetPropertyChangedSignal("Enabled")', 'node.children[child.Name]'):
            self.assertIn(token, effects)
        self.assertEqual(effects.count('GetDescendants()'), 1)
        for key in ('compositePathEvents', 'compositeRootChanges', 'compositeDiscoveryVisits',
                    'compositeEffectEvents', 'compositeEffectVisits', 'compositeEffectWrites'):
            self.assertIn(key, effects)
            self.assertIn(key, diagnostics)
        self.assertNotIn('compositeVisits', diagnostics)
        for token in ('Heartbeat', 'task.wait', 'task.spawn', 'RemoteEvent', 'Instance.new', 'record.desired'):
            self.assertNotIn(token, effects)
        self.assertNotIn('Workspace.DescendantAdded', effects)
        self.assertIn('location-composite-effects', read('system/control-center/mechanics/lod.py'))
        self.assertIn('LocationCompositeEffects.luau', read('system/control-center/mechanics/catalog.py'))
