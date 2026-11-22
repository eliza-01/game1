"""M431: successful floor transfers notify the owning camera once.

Static transport/ownership checks and numeric orbit examples, not Studio execution.
"""
from pathlib import Path
import math
import unittest

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


class HouseTeleportCameraM431(unittest.TestCase):
    def test_authoritative_destination_not_source_or_client(self):
        elevator = read('src/server/world/HouseElevatorService.luau')
        debug = read('src/server/world/HouseSocketService.luau').split('function Service.TeleportDebug', 1)[1].split('function Service.Start', 1)[0]
        for move in (elevator, debug):
            self.assertEqual(move.count('CameraSync.Align(player, character, targetFrame)'), 1)
            self.assertLess(move.index('if not targetFrame then'), move.index('character:PivotTo(targetFrame)'))
            self.assertLess(move.index('character:PivotTo(targetFrame)'), move.index('CameraSync.Align'))
            self.assertLess(move.index('controller.FacingDirection = targetFrame.LookVector'), move.index('CameraSync.Align'))
            self.assertLess(move.index('root.AssemblyAngularVelocity = Vector3.zero'), move.index('CameraSync.Align'))
        self.assertIn('Policy.DestinationSocket(floor, option.destination)', elevator)

    def test_server_client_version_and_lifecycle(self):
        heading = read('src/shared/character/CharacterCameraHeading.luau')
        server = read('src/server/character/CharacterCameraSync.luau')
        service = read('src/server/character/CharacterService.luau')
        client = read('src/client/character/CameraController.luau')
        self.assertIn('Heading.RemoteName = "CharacterCameraAlignV1"', heading)
        self.assertIn('event.Name = Heading.RemoteName', server)
        self.assertIn('WaitForChild(CameraHeading.RemoteName, 30)', client)
        self.assertIn('event.OnClientEvent:Connect(alignAfterTeleport)', client)
        self.assertLess(service.index('CharacterCameraSync.Start(remotes)'), service.index('Players.PlayerAdded:Connect'))
        self.assertIn('if player.Character ~= character then return end', server)
        self.assertIn('event:FireClient(player, character, targetFrame.LookVector)', server)
        self.assertNotIn('OnServerEvent', server)
        self.assertNotIn('FireAllClients', server)
        self.assertNotIn('RunService', server)

    def test_camera_updates_orbit_and_preserves_pitch_zoom(self):
        client = read('src/client/character/CameraController.luau')
        align = client.split('local function alignAfterTeleport', 1)[1].split('local function setCharacter', 1)[0]
        self.assertIn('movedCharacter ~= localPlayer.Character', align)
        self.assertIn('typeof(forward) ~= "Vector3"', align)
        self.assertIn('CameraHeading.Yaw(forward)', align)
        self.assertIn('if yaw == nil then return end', align)
        self.assertIn('clearAutoAim()', align)
        self.assertIn('targetYaw = yaw', align)
        self.assertIn('discardNextMouseDelta = rotating', align)
        self.assertNotIn('targetPitch =', align)
        self.assertNotIn('distance =', align)
        self.assertNotIn('camera.CFrame', align)
        self.assertIn('CFrame.Angles(0, targetYaw, 0)', client)
        self.assertIn('CFrame.Angles(targetPitch, 0, 0)', client)
        self.assertIn('GetRenderCFrame()', client)

    def test_pending_alignment_is_character_scoped(self):
        client = read('src/client/character/CameraController.luau')
        self.assertIn('pendingAlignment = {character = movedCharacter, yaw = yaw}', client)
        self.assertIn('if character ~= newCharacter or localPlayer.Character ~= newCharacter then return end', client)
        self.assertIn('pending.character == newCharacter then pending.yaw', client)
        self.assertIn('pendingAlignment.character == removingCharacter then pendingAlignment = nil', client)

    def test_heading_matches_camera_forward_for_all_quadrants(self):
        heading = read('src/shared/character/CharacterCameraHeading.luau')
        self.assertIn('return math.atan2(-x, -z)', heading)
        self.assertIn('if x * x + z * z < 1e-8 then return nil end', heading)
        self.assertIn('x ~= x or z ~= z', heading)
        # CFrame.Angles(0,yaw,0) rotates the camera's local -Z forward.
        for x,z in ((0,-1),(1,0),(0,1),(-1,0),(3,4),(-3,4),(3,-4),(-3,-4)):
            yaw = math.atan2(-x,-z)
            length = math.hypot(x,z)
            self.assertAlmostEqual(-math.sin(yaw), x/length)
            self.assertAlmostEqual(-math.cos(yaw), z/length)


if __name__ == '__main__':
    unittest.main()
