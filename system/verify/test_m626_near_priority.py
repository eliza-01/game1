"""Player-centered loading order: executable queue/work/async oracle."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]


class NearPriorityM626(unittest.TestCase):
    def test_priority_queue_work_and_async(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua:
            self.skipTest('Lua CLI unavailable')
        subprocess.run([lua, 'system/verify/lod_near_priority_m626.lua'], cwd=ROOT, check=True, timeout=30)

    def test_runtime_anchor_and_existing_policy(self):
        source = (ROOT/'src/client/world/LocationWorldStreamer.luau').read_text()
        for needle in ('Players.LocalPlayer', 'return root.Position, root', 'stage == "world"',
                       'loadPriority:Observe(localRecords, priorityPosition, Policy.SurfaceDistance',
                       'loadPriority:Sample(record, position, Policy.SurfaceDistance)',
                       'houseAdapter:YieldReadyOutside(ordered, loadPriority)',
                       'transition.variant ~= "UNLOADED" and not loadPriority:Allows(record)',
                       'runtimeWork:Begin(ordered, function(entry) return loadPriority:Allows(entry.record) end)',
                       'LodThresholdCache.Resolve(record, cameraPosition, Policy, cameraChanged)'):
            self.assertIn(needle, source)
        self.assertEqual(source.count('RunService.Heartbeat:Connect'), 1)
        priority = (ROOT/'src/client/world/LodLoadPriority.luau').read_text()
        for token in ('RunService', 'task.spawn', 'GetDescendants', 'Instance.new', 'PreloadAsync'):
            self.assertNotIn(token, priority)
