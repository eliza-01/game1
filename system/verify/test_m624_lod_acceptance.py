"""Runtime LOD acceptance instrumentation and authoring teardown contract."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


class LodAcceptanceM624(unittest.TestCase):
    def test_capture_oracle(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua:
            self.skipTest('Lua CLI unavailable')
        subprocess.run([lua, 'system/verify/lod_diagnostics_m624.lua'], cwd=ROOT, check=True, timeout=30)

    def test_capture_uses_existing_runtime_owner(self):
        streamer = read('src/client/world/LocationWorldStreamer.luau')
        self.assertEqual(streamer.count('RunService.Heartbeat:Connect'), 1)
        for token in ('diagnostics = LodDiagnostics.new()', 'runtimeWork.diagnostics = diagnostics',
                      'queue.diagnostics = diagnostics', 'houseAdapter.requests.diagnostics = diagnostics',
                      'diagnostics:Add("distanceResolves")', 'diagnostics:Add("workDistanceChecks")',
                      'diagnostics:Frame(dt, stats, os.clock()-captureStart)',
                      'if not active or not active.manifest then return false'):
            self.assertIn(token, streamer)
        capture = read('src/client/world/LodDiagnostics.luau')
        for forbidden in ('Heartbeat:Connect', 'RemoteEvent', 'task.spawn', 'GetDescendants'):
            self.assertNotIn(forbidden, capture)
        self.assertIn('enabled=false', capture)
        self.assertIn('local LIMIT = 12000', capture)
        self.assertIn('record.diagnosticDesiredAt', read('src/client/world/LodRuntimeWork.luau'))

    def test_authorized_mobile_debug_and_shared_panel(self):
        controller = read('src/client/dev/LodDebugController.luau')
        self.assertIn('not Access.ClientAllowed()', controller)
        self.assertIn('Dock.Bind("LD",launcher,panel,350,true,390)', controller)
        self.assertIn('Game1DebugPanelOpen', controller)
        self.assertIn('HttpService:JSONEncode(report)', controller)
        self.assertIn('Streamer.StartDiagnostics()', controller)
        self.assertIn('Streamer.FinishDiagnostics()', controller)
        profile = read('src/client/dev/DebugDockProfile.luau')
        self.assertIn('CD = 2, LD = 3', profile)
        self.assertIn('CD = 3, LD = 4', profile)
        init = read('src/client/init.client.luau')
        self.assertIn('if DebugAccess.ClientAllowed() then', init)
        self.assertIn('require(DevRoot:WaitForChild("LodDebugController")).Start()', init)
        self.assertNotIn('RemoteEvent', controller)

    def test_preview_teardown_disconnects_restores_and_destroys(self):
        preview = read('src/client/world/StudioLodPreviewAdapter.luau')
        self.assertIn('self.addedConnection = Workspace.DescendantAdded:Connect(add)', preview)
        self.assertIn('self.removingConnection = Workspace.DescendantRemoving:Connect', preview)
        teardown = preview.split('function Adapter:Destroy()', 1)[1]
        for token in ('self.addedConnection:Disconnect()', 'self.removingConnection:Disconnect()',
                      'restore(record)', 'self.records, self.inventory, self.managed = {}, {}, {}', 'self.folder:Destroy()'):
            self.assertIn(token, teardown)
        self.assertIn('state.preview:Destroy()', read('src/client/world/LocationWorldStreamer.luau'))


if __name__ == '__main__':
    unittest.main()
