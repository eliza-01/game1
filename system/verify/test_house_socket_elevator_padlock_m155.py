"""M155 contract/regression checks for server-owned house transitions.

These static checks complement Studio Play; no Roblox engine is available here.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


def source(path):
    return (ROOT / path).read_text(encoding="utf-8")


class HouseSocketM155(unittest.TestCase):
    def test_optional_elevator_floors_are_real_authored_sockets(self):
        contract = source("src/shared/world/HouseSocketContract.luau")
        for socket in ("elevator_02_socket", "elevator_03_socket", "house_floor_03_spawn_01_socket"):
            self.assertRegex(contract, rf'"{socket}"[^\n]+optional = true')
        authoring = source("system/control-center/real_estate/rig_features.py")
        self.assertIn("elevator_02_socket", authoring)
        self.assertIn("elevator_03_socket", authoring)
        registry = source("src/server/world/HouseSocketService.luau")
        self.assertIn("if not definition.optional then", registry)
        self.assertIn("Padlock.Ensure(house", registry)
        self.assertLess(registry.index("Padlock.Ensure(house"), registry.index("local function createPrompt("))

    def test_elevator_policy_directions_and_contiguous_floors(self):
        policy = source("src/shared/world/HouseElevatorPolicy.luau")
        self.assertIn('if not present[floor] then break end', policy)
        self.assertIn('if top == 2 and floor == 2 then', policy)
        self.assertIn('{key = "E", destination = 1', policy)
        self.assertIn('{key = "E", destination = floor + 1', policy)
        self.assertIn('if top >= 3 and floor > 1 then', policy)
        self.assertIn('{key = "F", destination = floor - 1', policy)
        self.assertIn('function Policy.Resolve(', policy)
        elevator = source("src/server/world/HouseElevatorService.luau")
        self.assertIn('local target = sockets[Policy.DestinationSocket(floor, option.destination)]', elevator)
        self.assertIn('if not target or not target.Parent then return false', elevator)
        self.assertIn('local root = SpatialRoot.Get(player)', elevator)
        self.assertIn('character:PivotTo(targetFrame)', elevator)
        self.assertIn('root.AssemblyLinearVelocity = Vector3.zero', elevator)
        self.assertNotIn('Workspace:GetDescendants()', elevator)

    def test_lock_transitions_are_server_authoritative_and_key_stub(self):
        lock = source("src/server/world/HousePadlockService.luau")
        self.assertIn('function Padlock.HasKey(player: Player): boolean', lock)
        self.assertIn('not RunService:IsStudio() or player:GetAttribute(Padlock.TestKeyAttribute) ~= false', lock)
        self.assertIn('if not Padlock.CanAttach(house, hasSocket, doorOpen, doorMoving) then', lock)
        self.assertIn('house:SetAttribute(ATTRIBUTE, false)', lock)
        self.assertIn('house:SetAttribute(ATTRIBUTE, true)', lock)
        runtime = source("src/server/world/HouseSocketService.luau")
        self.assertIn('if Padlock.IsAttached(house, hasPadlock) then return end', runtime)
        self.assertIn('primary.Enabled = not locked', runtime)
        self.assertIn('prompt.Enabled = locked', runtime)
        self.assertIn('part.Transparency = if locked then 0.4 else 1', runtime)
        self.assertIn('Door.IsMoving(house)', runtime)
        self.assertIn('Game1PadlockAttached', runtime)

    def test_server_validates_keys_client_never_sends_coordinates(self):
        server = source("src/server/world/HouseSocketService.luau")
        self.assertIn('interactionRemote.OnServerEvent:Connect(function(player, socket: any, key: any)', server)
        self.assertIn('if key ~= "E" and key ~= "F" then return end', server)
        self.assertIn('if definition.role ~= "elevator" and definition.role ~= "door" and key ~= "E" then return end', server)
        self.assertIn('if option.key == key then offered = true', server)
        self.assertIn('rootPosition(player)', server)
        self.assertIn('radiusFor(player, name) + (if definition.hoverRadius then 0 else 2)', server)
        self.assertIn('prompt.KeyboardKeyCode = if key == "F" then Enum.KeyCode.F else Enum.KeyCode.E', server)
        self.assertIn('createPrompt(socket, definition, option.key, option.action)', server)
        client = source("src/client/world/HouseSocketPromptController.luau")
        self.assertIn('remote:FireServer(socket, key)', client)
        self.assertNotIn('remote:FireServer(frame.Position)', client)
        self.assertIn('prompt.KeyboardKeyCode.Name', client)
        self.assertIn('prompt.Parent == selected.Parent', client)
        self.assertIn('selectedSocket', client)
        self.assertIn('key ~= "E" and key ~= "F"', client)

    def test_debug_height_doubled_and_door_pivot_unchanged(self):
        panel = source("src/client/dev/HouseSocketDebugController.luau")
        self.assertIn('math.min(1547, math.max(220, (height - 30) * 0.85))', panel)
        door = source("src/server/world/HouseDoorService.luau")
        self.assertIn('closed * CFrame.Angles(0, ANGLE, 0)', door)
        self.assertIn('door:PivotTo(frame)', door)
        self.assertIn('function Doors.IsMoving(', door)

if __name__ == '__main__':
    unittest.main()
