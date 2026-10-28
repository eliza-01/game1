"""M148 regression: authored socket discovery and event-driven placed house lifecycle.

The sample topology reflects the supplied Workspace tree (two level-4 houses
with DoorAssembly/DoorRig and HouseRig, 10 bones each). This is a source contract
test; Roblox engine behavior still requires Studio Play verification.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]

def source(relative):
    return (ROOT / relative).read_text(encoding="utf-8")

CONTRACT = "src/shared/world/HouseSocketContract.luau"
DISCOVERY = "src/server/world/HouseSocketDiscovery.luau"
SERVICE = "src/server/world/HouseSocketService.luau"

class WorkspaceHouseDiscoveryM148(unittest.TestCase):
    def test_real_workspace_socket_names_match_contract(self):
        contract = source(CONTRACT)
        definitions = set(re.findall(r'\{name = "([^"]+)", role = ', contract))
        authored = {
            "door_01_handle_inside_socket", "door_01_handle_outside_socket",
            "door_01_hinge_socket", "door_01_padlock_01_socket",
            "chest_01_socket", "chimney_01_socket", "elevator_01_socket",
            "house_floor_01_spawn_01_socket", "house_floor_02_spawn_01_socket",
            "land_spawn_01_socket",
        }
        self.assertEqual(len(authored), 10)
        self.assertEqual(authored - {"door_01_hinge_socket"}, definitions - {
            "elevator_02_socket", "elevator_03_socket", "house_floor_03_spawn_01_socket"
        })

    def test_studio_fallback_is_explicit_and_production_remains_managed(self):
        discovery = source(DISCOVERY)
        self.assertIn('instance:GetAttribute("Game1RealEstateTemplate") == true', discovery)
        self.assertIn('Game1RealEstateSlug', discovery)
        self.assertIn('if not RunService:IsStudio() then return false end', discovery)
        self.assertIn('instance:FindFirstChild("HouseRig")', discovery)
        self.assertIn('Contract.Get(descendant.Name)', discovery)
        self.assertIn('function Discovery.OwnerOf(instance: Instance)', discovery)
        self.assertNotIn('Workspace.Plots', discovery)
        self.assertNotIn('Workspace.Houses', discovery)
        self.assertNotIn('Instance.new("Bone")', discovery)

    def test_registration_is_single_pass_and_failed_house_is_isolated(self):
        service = source(SERVICE)
        self.assertIn('local socketByName: {[string]: Attachment} = {}', service)
        self.assertIn('local duplicateNames: {[string]: boolean} = {}', service)
        self.assertIn('for _, descendant in house:GetDescendants() do', service)
        self.assertIn('local ok, err = pcall(register, house)', service)
        self.assertIn('registration failed ', service)
        self.assertIn('prompt.Parent = socket', service)
        self.assertIn('GetDebugStatus', service)

    def test_late_identity_and_sockets_have_deduplicated_rebuild(self):
        service = source(SERVICE)
        self.assertIn('GetAttributeChangedSignal("Game1RealEstateSlug")', service)
        self.assertIn('GetAttributeChangedSignal("Game1RealEstateTemplate")', service)
        self.assertIn('Workspace.DescendantAdded:Connect', service)
        self.assertIn('Workspace.DescendantRemoving:Connect', service)
        self.assertIn('if refreshQueued[house] then return end', service)
        self.assertIn('for _, connection in connections do connection:Disconnect() end', service)
        self.assertNotIn('RunService.Heartbeat', service)
        client = source('src/client/dev/HouseSocketDebugController.luau')
        self.assertIn('RunService:IsStudio() and ancestor:FindFirstChild("HouseRig")', client)

if __name__ == '__main__':
    unittest.main()
