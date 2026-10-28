"""M150: custom ControllerManager character support without changing the door rig."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def text(path):
    return (ROOT / path).read_text(encoding="utf-8")


class HouseSocketCustomCharacterM150(unittest.TestCase):
    def test_shared_resolver_handles_controller_manager_and_humanoid(self):
        body = text("src/shared/character/CharacterSpatialRoot.luau")
        self.assertIn('"CustomCharacter"', body)
        self.assertIn('"LifeState") ~= "Alive"', body)
        self.assertIn('"RootCollider"', body)
        self.assertIn('"NavigationRoot"', body)
        self.assertIn('"HumanoidRootPart"', body)
        self.assertIn('"Humanoid"', body)

    def test_server_reach_and_teleport_use_same_root(self):
        body = text("src/server/world/HouseSocketService.luau")
        self.assertIn('local SpatialRoot = require(', body)
        self.assertIn('local root = SpatialRoot.Get(player)', body)
        self.assertIn('local pos = rootPosition(player)', body)
        self.assertIn('radiusFor(player, name) + 2', body)
        self.assertIn('character:PivotTo(getFrame(socket)', body)
        self.assertIn('root.AssemblyLinearVelocity = Vector3.zero', body)
        self.assertIn('root.AssemblyAngularVelocity = Vector3.zero', body)
        self.assertNotIn('not humanoid or humanoid.Health', body)

    def test_custom_f_remote_still_has_server_authority(self):
        server = text("src/server/world/HouseSocketService.luau")
        client = text("src/client/world/HouseSocketPromptController.luau")
        self.assertIn('interactionRemote.OnServerEvent:Connect', server)
        self.assertIn('typeof(socket) ~= "Instance"', server)
        self.assertIn('entry.sockets[socket.Name] ~= socket', server)
        self.assertIn('handleInteraction(house, socket.Name, player)', server)
        self.assertIn('cooldown[player]', server)
        self.assertIn('if SpatialRoot.IsCustom(player) then return end', client)
        self.assertIn('remote:FireServer(socket)', client)
        self.assertNotIn('remote:FireServer(frame.Position)', client)
        self.assertIn('UserInputService.InputBegan:Connect', client)

    def test_prompt_selection_scans_cache_only_and_has_radius(self):
        client = text("src/client/world/HouseSocketPromptController.luau")
        method = client.split('local function nearestCustomPrompt', 1)[1].split('local function updateCustomPrompt', 1)[0]
        self.assertIn('for prompt in prompts do', method)
        self.assertIn('distance > radius(name)', method)
        self.assertIn('camera:WorldToViewportPoint', method)
        self.assertNotIn('Workspace:GetDescendants()', method)
        self.assertIn('elapsed < 0.1', client)

    def test_door_service_is_not_changed_by_character_hotfix(self):
        # Existing rigid-model pivot policy stays as authored; fix the rig separately.
        door = text("src/server/world/HouseDoorService.luau")
        self.assertIn('Game1DoorPivotMode', door)
        self.assertIn('closed * CFrame.Angles(0, ANGLE, 0)', door)
        self.assertNotIn('hingePosition', door)

if __name__ == '__main__':
    unittest.main()
