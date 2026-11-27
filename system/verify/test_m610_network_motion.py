from pathlib import Path
import shutil
import subprocess
import unittest
ROOT = Path(__file__).resolve().parents[2]
def read(p): return (ROOT/p).read_text(encoding='utf-8')
class NetworkMotion(unittest.TestCase):
    def test_statistics(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua: self.skipTest('Lua CLI unavailable')
        subprocess.run([lua,'system/verify/network_motion_m610.lua'],cwd=ROOT,check=True,timeout=15)
    def test_read_only_capture(self):
        s=read('src/shared/dev/NetworkMotionCapture.luau')
        for x in ('root.Position','root:GetRenderCFrame().Position','root.AssemblyLinearVelocity','sampledAt - session.previousSampledAt','session.player.Character ~= root.Parent'):
            self.assertIn(x,s)
        for x in ('SetNetworkOwner',':PivotTo(','.CFrame =','.AssemblyLinearVelocity =','FireServer','FireClient'):
            self.assertNotIn(x,s)
    def test_bounded_authorized_server(self):
        s=read('src/server/dev/NetworkMotionDiagnosticService.luau')
        for x in ('Access.ServerEnabled()','Access.ServerAllowed(player)','count >= LIMIT','COOLDOWN = 12','LIMIT = 2','connection:Disconnect()','Players.PlayerRemoving','GetServerTimeNow()'):
            self.assertIn(x,s)
        self.assertIn('if not connection then connection = RunService.Heartbeat:Connect(tick) end',s)
        self.assertIn('if publishedDebugEnabled() then require(dev:WaitForChild("NetworkMotionDiagnosticService")).Start() end',read('src/server/bootstrap/ServiceCatalog.luau'))
    def test_existing_debug_panel_only(self):
        s=read('src/client/dev/NetworkMotionDiagnosticView.luau')
        for x in ('event:FireServer(request,selected.UserId)','RunService.RenderStepped:Connect','connection:Disconnect()','eventConnection:Disconnect()','task.delay(17','[NETMOTION]','GetServerTimeNow()'):
            self.assertIn(x,s)
        self.assertEqual(s.count('FireServer('),1)
        self.assertIn('NetworkMotionDiagnosticView',read('src/client/dev/CameraDebugController.luau'))

    def test_owner_capture_bounded_and_authorized(self):
        server=read('src/server/dev/NetworkMotionDiagnosticService.luau')
        for x in ('session.capture.player == player','session.ownerId == userId','Statistics.ValidateOwner(report, session.capture.startAt)','session.capture.endAt + 2','session.capture.player == target','Access.ServerAllowed(target)'):
            self.assertIn(x,server)
        owner=read('src/client/dev/NetworkMotionOwnerCapture.luau')
        for x in ('kind ~= "ownerStart" or connection','Capture.New(Players.LocalPlayer','connection:Disconnect()','event:FireServer("owner", id, Capture.Finish','connection == thisConnection'):
            self.assertIn(x,owner)
        self.assertIn('NetworkMotionOwnerCapture',read('src/client/dev/CameraDebugController.luau'))
        self.assertIn('clientReport and serverReport and (selfTarget or ownerDone)',read('src/client/dev/NetworkMotionDiagnosticView.luau'))
