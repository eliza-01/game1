"""M149: runtime socket reconciliation after late authoring placement.

Structural tests cannot run Roblox Studio engine. End-to-end confirmation still
requires live Play; the contract here guards the debug repair path and UX.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
def source(name):
    return (ROOT/name).read_text(encoding='utf-8')

class HouseSocketReconcileM149(unittest.TestCase):
    def test_debug_request_repairs_before_reporting(self):
        service=source('src/server/world/HouseSocketService.luau')
        transport=source('src/server/dev/HouseSocketDebugService.luau')
        self.assertIn('function Service.Reconcile()',service)
        self.assertIn('if not RunService:IsStudio() or not reconcileWorld then',service)
        self.assertIn('local function needsRepair(house: Model, entry: Entry)',service)
        self.assertIn('if entry.sockets[descendant.Name] ~= descendant then return true end',service)
        self.assertIn('not descendant:FindFirstChild("Game1HouseInteraction")',service)
        self.assertIn('local metrics = Service.Reconcile()',transport)
        self.assertLess(transport.index('Service.Reconcile()'), transport.index('Service.GetDebugStatus(player)'))
        self.assertIn('Service.Reconcile()\n    local house, socket = Service.FindNearest',service)

    def test_scan_is_manual_only_and_tracks_actual_authored_bones(self):
        service=source('src/server/world/HouseSocketService.luau')
        self.assertIn('reconcileWorld = reconcile',service)
        self.assertIn('local startup = reconcile()',service)
        self.assertIn('result.authored = authored',service)
        self.assertIn('if socket:IsA("Attachment") and Contract.Get(socket.Name) then',service)
        self.assertNotIn('RunService.Heartbeat',service)
        self.assertNotIn('Instance.new("Bone")',service)

    def test_studio_only_visibility_preview_and_debug_metrics(self):
        service=source('src/server/world/HouseSocketService.luau')
        panel=source('src/client/dev/HouseSocketDebugController.luau')
        self.assertIn('prompt.RequiresLineOfSight = true',service)
        self.assertIn('if RunService:IsStudio() then prompt.RequiresLineOfSight = false end',service)
        self.assertIn('metrics.prompts',panel)
        self.assertIn('metrics.authored',panel)
        discovery=source('src/server/world/HouseSocketDiscovery.luau')
        self.assertIn('if isTemplate and not isStudio then return false end',discovery)
        self.assertIn('if not isTemplate and typeof(slug)',discovery)
        self.assertIn('local result = invoke("GetTestHouseSockets")',panel)

if __name__ == '__main__':
    unittest.main()
