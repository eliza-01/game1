"""Threshold cache and persistent queue: executable oracle and ownership contracts."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


class LodTransitionQueueM620(unittest.TestCase):
    def test_threshold_oracle_and_queue_lifecycle(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua:
            self.skipTest('Lua CLI unavailable; run standalone oracle when installed')
        subprocess.run([lua, 'system/verify/lod_transition_queue_m620.lua'], cwd=ROOT, check=True, timeout=30)

    def test_streamer_reconciles_pending_even_when_stationary(self):
        source = read('src/client/world/LocationWorldStreamer.luau')
        tick = source.split('RunService.Heartbeat:Connect', 1)[1]
        self.assertIn('queue:Attempted(transition)', source)
        self.assertIn('record.actual = if replacement then variant else "UNLOADED"', source)
        for needle in ('queue:Begin(priorityPosition, cameraChanged or priorityReset)',
                       'candidates:Collect(cameraPosition, cameraChanged)',
                       'LodThresholdCache.Resolve(record, cameraPosition, Policy, cameraChanged)',
                       'record.part:IsDescendantOf(Workspace)', 'not available(record, status, prototype, metadata, variant)',
                       'queue:Remove(record)', 'continue', 'queue:Set(record, variant, prototype, metadata, force)',
                       'queue:Ordered(function(record, position)', 'runtimeWork:Step(callbacks)',
                       'queue:Remove(record)', 'houseAdapter:Observe('):
            self.assertIn(needle, tick)
        self.assertNotIn('local transitions = {}', tick)
        self.assertNotIn('if not cameraChanged then return', tick)
        self.assertLess(tick.index('queue:Begin'), tick.index('queue:Set'))
        self.assertLess(tick.index('queue:Set'), tick.index('queue:Ordered'))
        self.assertIn('runtimeWork:Begin(ordered,', tick)
        self.assertIn('runtimeWork:Step(callbacks)', tick)

    def test_pure_helpers_no_new_runtime_ownership(self):
        for name in ('LodThresholdCache', 'LodTransitionQueue'):
            text = read(f'src/client/world/{name}.luau')
            for forbidden in ('Heartbeat', 'Raycast', 'RemoteEvent', 'Instance.new', 'task.spawn', 'GetDescendants'):
                self.assertNotIn(forbidden, text)
        self.assertIn('policy.Resolve(distance, previous, record.distances, record.mode)', read('src/client/world/LodThresholdCache.luau'))
