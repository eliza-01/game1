"""M622 Runtime Location jobs, operation budgets and lifecycle contract."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]


def source(name):
    return (ROOT / 'src/client/world' / name).read_text(encoding='utf-8')


class IncrementalAssemblyM622(unittest.TestCase):
    def test_scheduler_oracle(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua:
            self.skipTest('Lua CLI unavailable')
        args = [lua, 'system/verify/lod_runtime_work_m622.lua']
        if Path(lua).name == 'texlua':
            args.insert(1, '--luaonly')
        subprocess.run(args, cwd=ROOT, check=True, timeout=30)

    def test_runtime_uses_jobs_not_synchronous_clone_loop(self):
        streamer = source('LocationWorldStreamer.luau')
        self.assertIn('runtimeWork:Begin(ordered,', streamer)
        self.assertIn('runtimeWork:Step(callbacks)', streamer)
        self.assertIn('LodAssembly.PrepareSingle', streamer)
        self.assertIn('LodAssembly.Prepare(', streamer)
        self.assertIn('LocationCompositeVisual.Prepare(', streamer)
        self.assertIn('transition.epoch ~= (record.prototypeEpoch or 0)', streamer)
        self.assertIn('LodThresholdCache.ResolveAt(record, LodThresholdCache.Measure(record, cameraPosition, Policy)', streamer)
        self.assertIn('queue.entries[record] ~= transition', streamer)
        self.assertIn('state.runtimeWork:Destroy()', streamer)
        self.assertNotIn('LodAssembly.Create(', streamer)
        self.assertNotIn('math.min(MAX_CHANGES_PER_TICK', streamer)
        self.assertEqual(streamer.count('RunService.Heartbeat:Connect'), 1)

    def test_staging_welds_and_commit(self):
        composite = source('LocationCompositeVisual.luau')
        before, commit = composite.split('function Adapter.BindForCommit', 1)
        self.assertNotIn('joint.Part0 =', before)
        self.assertIn('job.root:FindFirstChild(entry.name, true) ~= entry.proxy', commit)
        self.assertIn('entry.part.CFrame = entry.proxy.CFrame', commit)
        self.assertIn('entry.joint.Part0 = entry.proxy', commit)
        streamer = source('LocationWorldStreamer.luau')
        self.assertLess(streamer.index('replacement.Parent = job.root or folder'),
                        streamer.index('work:Retire(record.part)'))
        self.assertIn('record.actual = if replacement then variant else "UNLOADED"', streamer)
        self.assertIn('compositeEffects:ActualChanged(record)', streamer)

    def test_preview_reuses_job_builder(self):
        assembly = source('LocationLodAssembly.luau')
        self.assertIn('function Assembly.Prepare(', assembly)
        self.assertIn('bounds(targetFrame, targetParts, job)', assembly)
        self.assertIn('if job then job:Unit() end', assembly)
        self.assertIn('return job:Finish()', assembly)
        self.assertIn('LodAssembly.Create(', source('StudioLodPreviewAdapter.luau'))
        for name in ('LodAssemblyJob.luau', 'LodRuntimeWork.luau'):
            self.assertNotIn('Heartbeat:Connect', source(name))
            self.assertNotIn('task.spawn(', source(name))
