"""M147: Studio debug visibility, lifecycle and read-safe runtime texture checks."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
def source(path):
    return (ROOT / path).read_text(encoding='utf-8')

class HouseSocketRuntimeM147(unittest.TestCase):
    def test_debug_panel_is_independent_of_loadout_remotes(self):
        init = source('src/client/init.client.luau')
        ui = source('src/client/dev/HouseSocketDebugController.luau')
        loadout = source('src/client/dev/TestLoadoutController.luau')
        self.assertLess(init.index('HouseSocketDebugController.Start()'), init.index('TestLoadoutController.Start()'))
        self.assertIn('StudioDebugDock.ButtonPosition("HS")', ui)
        self.assertIn('StudioDebugDock.WindowPosition("HS", 390)', ui)
        self.assertIn('function Debug.AttachLauncher', ui)
        self.assertIn('HouseSocketDebugController.AttachLauncher', loadout)
        self.assertIn('FindFirstChild(remoteName)', ui)
        self.assertNotIn('WaitForChild("GetTestHouseSockets"', ui)
        self.assertIn('HS = 4', source('src/client/dev/StudioDebugDock.luau'))

    def test_server_explicitly_reports_registration_and_handles_late_sockets(self):
        runtime = source('src/server/world/HouseSocketService.luau')
        self.assertIn('ready · %d house(s) · %d socket(s) · %d prompt(s)', runtime)
        self.assertIn('Workspace.DescendantAdded', runtime)
        self.assertIn('elseif descendant:IsA("Attachment") and Contract.Get(descendant.Name)', runtime)
        self.assertIn('scheduleRefresh(house)', runtime)
        self.assertIn('if refreshQueued[house] then return end', runtime)
        self.assertNotIn('RunService.Heartbeat', runtime)

    def test_runtime_must_not_touch_plugin_only_surface_properties(self):
        runtime = source('src/server/world/EnvironmentAssetVisuals.luau')
        self.assertNotIn('.ColorMap', runtime)
        self.assertNotIn('.AlphaMode', runtime)
        self.assertIn('if mesh:FindFirstChildOfClass("SurfaceAppearance") then return false end', runtime)
        self.assertIn('mesh.TextureID = uri', runtime)
        authoring = source('system/studio-plugin/modules/StudioTextureAppearance.luau')
        self.assertIn('surface.ColorMap = uri', authoring)

if __name__ == '__main__':
    unittest.main()
