"""M159 contract regressions, complement Studio Play tests.

Lua services are runtime-owned; these source checks validate direction, authority
and UI wiring without claiming to execute Roblox Engine-side transitions.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]

def src(path):
    return (ROOT / path).read_text(encoding='utf-8')

class HouseSocketM159(unittest.TestCase):
    def test_descending_to_first_floor_uses_authored_spawn_not_elevator(self):
        policy = src('src/shared/world/HouseElevatorPolicy.luau')
        self.assertIn('function Policy.DestinationSocket(_sourceFloor: number, destination: number): string', policy)
        self.assertIn('if destination == 1 then', policy)
        self.assertIn('return "house_floor_01_spawn_01_socket"', policy)
        self.assertIn('return Policy.SocketName(destination)', policy)
        mover = src('src/server/world/HouseElevatorService.luau')
        self.assertIn('sockets[Policy.DestinationSocket(floor, option.destination)]', mover)
        self.assertIn('if not target or not target.Parent then return false', mover)
        self.assertIn('target.TransformedWorldCFrame', mover)
        self.assertIn('Orientation.Upright(if target:IsA("Bone")', mover)
        self.assertIn('target:IsA("Bone"), 3)', mover)
        self.assertIn('root.AssemblyAngularVelocity = Vector3.zero', mover)

    def test_both_handles_offer_e_open_and_f_lock_only_when_closed(self):
        server = src('src/server/world/HouseSocketService.luau')
        self.assertIn('for _, name in {"door_01_handle_inside_socket", "door_01_handle_outside_socket"}', server)
        self.assertIn('primary.Enabled = not locked', server)
        self.assertIn('alternate.Enabled = canAttach', server)
        self.assertIn('Padlock.CanAttach(house, hasPadlock, open, moving)', server)
        self.assertIn('createPrompt(socket, definition, "F", "Навесить замок · ключ")', server)
        self.assertIn('if definition.role == "door" and entry.sockets["door_01_padlock_01_socket"] then', server)
        self.assertIn('if definition.role == "door" and key == "F" then', server)
        self.assertIn('Padlock.Toggle(house, player, true, open, Door.IsMoving(house))', server)
        self.assertIn('Padlock.IsAttached(house, hasPadlock) then return end', server)
        self.assertIn('radiusFor(player, name) + (if definition.hoverRadius then 0 else 2)', server)
        self.assertIn('cooldown[player]', server)
        self.assertIn('prompt.Enabled = locked -- Re-attach only through F', server)

    def test_f_not_offered_while_door_moves_and_reenabled_on_completion(self):
        door = src('src/server/world/HouseDoorService.luau')
        server = src('src/server/world/HouseSocketService.luau')
        lock = src('src/server/world/HousePadlockService.luau')
        self.assertIn('door:SetAttribute("Game1DoorMoving", true)', door)
        self.assertIn('door:SetAttribute("Game1DoorMoving", false)', door)
        self.assertIn('"Game1DoorOpen", "Game1DoorMoving"', server)
        self.assertIn('and not doorOpen and not doorMoving', lock)
        self.assertIn('if not Padlock.HasKey(player) then', lock)

    def test_key_debug_is_server_written_and_studio_scoped(self):
        lock = src('src/server/world/HousePadlockService.luau')
        server = src('src/server/world/HouseSocketService.luau')
        debug = src('src/server/dev/HouseSocketDebugService.luau')
        ui = src('src/client/dev/HouseSocketDebugController.luau')
        self.assertIn('Padlock.TestKeyAttribute = "Game1HouseTestKeyOwned"', lock)
        self.assertIn('not RunService:IsStudio() or player:GetAttribute', lock)
        self.assertIn('player:SetAttribute(Padlock.TestKeyAttribute, owned)', lock)
        self.assertIn('typeof(owned) ~= "boolean"', server)
        self.assertIn('SetTestHouseKeyOwned', debug)
        self.assertIn('KEY: OWN', ui)
        self.assertIn('KEY: LOST', ui)
        self.assertIn('SetTestHouseKeyOwned', ui)
        self.assertIn('result.keyOwned ~= false', ui)

    def test_client_one_badge_per_socket_with_colored_key(self):
        client = src('src/client/world/HouseSocketPromptController.luau')
        self.assertIn('local visible: {[Attachment]: BillboardGui} = {}', client)
        self.assertIn('Game1HouseInteractionAlternate', client)
        self.assertIn('for _, name in {"Game1HouseInteraction", "Game1HouseInteractionAlternate"}', client)
        self.assertIn('text.RichText = true', client)
        self.assertIn('local colored = escaped:gsub("ключ",', client)
        self.assertIn('"#4DD8A8" else "#FF6E6E"', client)
        self.assertIn('remote:FireServer(socket, key)', client)
        self.assertIn('prompt.Parent == selected.Parent', client)
        self.assertIn('function Controller.SetRadius(', client)

    def test_panel_target_height_doubled_but_safe_for_viewport(self):
        debug = src('src/client/dev/HouseSocketDebugController.luau')
        self.assertIn('math.min(1547, math.max(220, (height - 30) * 0.85))', debug)
        self.assertIn('GetPropertyChangedSignal("ViewportSize")', debug)
        self.assertIn('scroll.AutomaticCanvasSize = Enum.AutomaticSize.Y', debug)

if __name__ == '__main__':
    unittest.main()
