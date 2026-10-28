"""M160 routing/interaction debug contract. Static: Studio Play still required."""
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[2]
def code(path): return (ROOT / path).read_text(encoding='utf-8')

class M160FloorAndAim(unittest.TestCase):
    def test_both_authored_floor_spawns_are_arrival_targets(self):
        policy = code('src/shared/world/HouseElevatorPolicy.luau')
        self.assertIn('if destination == 1 then return "house_floor_01_spawn_01_socket" end', policy)
        self.assertIn('if destination == 2 then return "house_floor_02_spawn_01_socket" end', policy)
        self.assertIn('return Policy.SocketName(destination)', policy)
        service = code('src/server/world/HouseElevatorService.luau')
        self.assertIn('sockets[Policy.DestinationSocket(floor, option.destination)]', service)
        self.assertIn('if option.destination == 1 or option.destination == 2 then', service)
        self.assertIn('target:IsA("Bone"), 3)', service)
        self.assertIn('if not target or not target.Parent then return false', service)

    def test_two_independent_radii_and_studio_only_debug(self):
        contract = code('src/shared/world/HouseSocketContract.luau')
        self.assertIn('hoverRadius: number?', contract)
        for n in (1, 2, 3):
            self.assertIn(f'"elevator_{n:02d}_socket", role = "elevator", hoverRadius = 5', contract)
        self.assertIn('function Contract.HoverRadiusAttribute(', contract)
        self.assertIn('Contract.MaxHoverRadius = 16', contract)
        server = code('src/server/world/HouseSocketService.luau')
        self.assertIn('function Service.SetDebugHoverRadius(', server)
        self.assertIn('not definition.hoverRadius', server)
        self.assertIn('not RunService:IsStudio()', server)
        self.assertIn('player:SetAttribute(Contract.HoverRadiusAttribute(name), hoverRadius)', server)
        self.assertIn('hoverRadius = hoverRadiusFor(player, definition.name)', server)
        self.assertIn('if definition.hoverRadius then 0 else 2', server)
        bridge = code('src/server/dev/HouseSocketDebugService.luau')
        self.assertIn('SetTestHouseSocketHoverRadius', bridge)
        self.assertIn('Service.SetDebugHoverRadius(player, name, radius)', bridge)

    def test_aim_is_3d_center_reticle_ray_volume_not_pixel_threshold(self):
        aim = code('src/shared/world/HouseSocketAimPolicy.luau')
        self.assertIn('function Aim.RaySphereEntry(', aim)
        self.assertIn('relative:Dot(direction)', aim)
        self.assertIn('sideSq > radiusSq', aim)
        self.assertIn('forward < -radius', aim)
        client = code('src/client/world/HouseSocketPromptController.luau')
        self.assertIn('camera:ViewportPointToRay(viewport.X * 0.5, viewport.Y * 0.5)', client)
        self.assertIn('Aim.RaySphereEntry(ray.Origin, ray.Direction, frame.Position, hoverRadius(name))', client)
        self.assertNotIn('Magnitude > 140', client)
        self.assertIn('return selectedOther', client)
        self.assertIn('if definition and definition.hoverRadius then 0 else radius(name)', client)
        self.assertIn('not SpatialRoot.IsCustom(player) and not definition.hoverRadius', client)
        self.assertIn('remote:FireServer(socket, key)', client)

    def test_debug_panel_shorter_and_renders_both_spheres(self):
        ui = code('src/client/dev/HouseSocketDebugController.luau')
        self.assertIn('math.min(1547, math.max(220, (height - 30) * 0.85))', ui)
        self.assertIn('Game1SocketRadiusPreview', ui)
        self.assertIn('Game1SocketAimPreview', ui)
        self.assertIn('CanQuery = false', ui)
        self.assertIn('aimPreviews', ui)
        self.assertIn('USE · reach', ui)
        self.assertIn('AIM · hover', ui)
        self.assertIn('SetTestHouseSocketHoverRadius', ui)
        self.assertIn('scroll.AutomaticCanvasSize = Enum.AutomaticSize.Y', ui)

if __name__ == '__main__': unittest.main()
