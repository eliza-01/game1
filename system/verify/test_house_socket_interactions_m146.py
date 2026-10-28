"""M146: contract and layering checks for Real Estate socket interactions."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'src'

class HouseSocketInteractions(unittest.TestCase):
    def text(self, path):
        return (SRC / path).read_text(encoding='utf8')

    def test_blender_socket_names_have_explicit_handlers(self):
        shared = self.text('shared/world/HouseSocketContract.luau')
        names = [
            'door_01_handle_inside_socket', 'door_01_handle_outside_socket',
            'door_01_padlock_01_socket', 'door_01_hinge_socket',
            'chimney_01_socket', 'elevator_01_socket', 'chest_01_socket',
            'house_floor_01_spawn_01_socket', 'house_floor_02_spawn_01_socket',
            'land_spawn_01_socket',
        ]
        for name in names:
            if name == 'door_01_hinge_socket':
                self.assertIn(name, (ROOT / 'system/studio-plugin/modules/StudioRealEstateModel.luau').read_text(encoding='utf8'))
            else:
                self.assertIn(name, shared)
        self.assertEqual(shared.count('interact = true'), 5)
        self.assertEqual(shared.count('interact = false'), 4)
        self.assertIn('MinDebugRadius = 2',shared)
        self.assertIn('MaxDebugRadius = 30',shared)

    def test_proximity_is_authoritatively_validated(self):
        runtime = self.text('server/world/HouseSocketService.luau')
        self.assertIn('prompt.KeyboardKeyCode = Enum.KeyCode.F', runtime)
        self.assertIn('prompt.Style = Enum.ProximityPromptStyle.Custom',runtime)
        self.assertIn('prompt.RequiresLineOfSight = true',runtime)
        self.assertIn('radiusFor(player, name) + 2', runtime)
        self.assertIn('rootPosition(player)', runtime)
        self.assertIn('cooldown[player]', runtime)
        self.assertIn('if not RunService:IsStudio()',runtime)
        self.assertIn('definition.role ~= "spawn"',runtime)
        self.assertIn('Workspace.DescendantAdded',runtime)
        self.assertIn('for house, entry in registered',runtime)
        self.assertNotIn('ProximityPrompt.Triggered:Connect',runtime)

    def test_moving_door_and_stubs_are_independent(self):
        door = self.text('server/world/HouseDoorService.luau')
        visuals = self.text('server/world/HouseSocketEffects.luau')
        self.assertIn('door:PivotTo(frame)', door)
        self.assertIn('Game1DoorClosedWorldPivot',door)
        self.assertIn('clearAnimation(door)',door)
        self.assertNotIn('Bone.Transform',door.split('function Doors.Toggle')[1])
        self.assertIn('Instance.new("Part")',visuals)
        self.assertIn('Instance.new("WeldConstraint")',visuals)
        self.assertIn('Instance.new("ParticleEmitter")',visuals)
        self.assertIn('emitter.Enabled = true', visuals)

    def test_client_ui_and_debug_are_isolated(self):
        hud=self.text('client/world/HouseSocketPromptController.luau')
        debug=self.text('client/dev/HouseSocketDebugController.luau')
        loadout=self.text('client/dev/TestLoadoutController.luau')
        for required in ['Instance.new("BillboardGui")','"Game1HousePrompt"','"F"',
                         'PromptShown:Connect','PromptHidden:Connect','ActionText']:
            self.assertIn(required,hud)
        self.assertIn('GetTestHouseSockets',debug)
        self.assertIn('SetTestHouseSocketRadius',debug)
        self.assertIn('TeleportTestHouseSpawn',debug)
        self.assertIn('RANGES: OFF',debug)
        self.assertIn('updateConnection = RunService.Heartbeat:Connect',debug)
        self.assertIn('for socket in tracked',debug)
        self.assertNotIn('Workspace:GetDescendants() do',debug.split('local function updatePreview()')[1])
        self.assertIn('HouseSocketDebugController.AttachLauncher(body, 428)',loadout)
        self.assertIn('HouseSocketPromptController.Start()',self.text('client/init.client.luau'))
        server=self.text('server/dev/HouseSocketDebugService.luau')
        self.assertIn('not RunService:IsStudio()',server)
        self.assertIn('Service.TeleportDebug',server)

    def test_failure_is_visible_when_import_culls_unweighted_sockets(self):
        runtime=self.text('server/world/HouseSocketService.luau')
        self.assertIn('Game1RuntimeMissingSockets',runtime)
        self.assertIn('if duplicate or not found then',runtime)
        self.assertNotIn('Instance.new("Bone")',runtime)

if __name__ == '__main__': unittest.main()
