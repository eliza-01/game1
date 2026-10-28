"""M161 source contracts plus independent geometry examples. Studio Play remains necessary."""
from pathlib import Path
import math
import unittest

ROOT = Path(__file__).resolve().parents[2]

def source(path):
    return (ROOT / path).read_text(encoding="utf-8")


def ray_sphere_entry(origin, direction, center, radius):
    """Specification mirror of the 3D ray/sphere test, not a Luau execution."""
    delta = tuple(c - o for c, o in zip(center, origin))
    forward = sum(a*b for a,b in zip(delta, direction))
    if forward < -radius: return None
    nearest = tuple(o + d*max(0,forward) for o,d in zip(origin, direction))
    side_sq = sum((c - n)**2 for c,n in zip(center,nearest))
    if side_sq > radius**2: return None
    dist = math.sqrt(sum(x*x for x in delta))
    if dist < radius:
        core = min(radius*.5, 2)
        if forward <= 0 or side_sq > core**2: return None
        return forward
    return max(0,forward - math.sqrt(max(0,radius**2-side_sq)))


class M161ReticleRaycast(unittest.TestCase):
    def test_both_aim_targets_have_independent_use_and_aim(self):
        contract = source('src/shared/world/HouseSocketContract.luau')
        self.assertIn('"chest_01_socket", role = "chest", action = "Открыть сундук", radius = 8, hoverRadius = 4', contract)
        for n in (1,2,3):
            self.assertIn(f'"elevator_{n:02d}_socket", role = "elevator", hoverRadius = 5', contract)
        server = source('src/server/world/HouseSocketService.luau')
        self.assertIn('if not definition or not definition.hoverRadius then return nil end', server)
        self.assertIn('if not RunService:IsStudio() or not definition or not definition.hoverRadius then', server)
        self.assertIn('radiusFor(player, name) + (if definition.hoverRadius then 0 else 2)', server)

    def test_aim_uses_headshot_center_ray_not_free_mouse(self):
        aim = source('src/client/combat/AimPoseController.luau')
        prompt = source('src/client/world/HouseSocketPromptController.luau')
        expected = 'camera:ViewportPointToRay(viewport.X * 0.5, viewport.Y * 0.5)'
        self.assertIn(expected, aim)
        self.assertIn(expected, prompt)
        self.assertNotIn('UserInputService:GetMouseLocation()', prompt)
        self.assertIn('Aim.RaySphereEntry(ray.Origin, ray.Direction, frame.Position, hoverRadius(name))', prompt)
        self.assertIn('Occlusion.IsClear(ray.Origin, ray.Direction, aimEntry, player.Character)', prompt)

    def test_one_real_raycast_without_queryable_fake_targets(self):
        occlusion = source('src/client/world/HouseSocketAimOcclusion.luau')
        self.assertIn('Workspace:Raycast(origin, direction * distance, params)', occlusion)
        self.assertIn('params.FilterDescendantsInstances = if character then {character} else {}', occlusion)
        self.assertIn('entryDistance - 0.05', occlusion)
        self.assertNotIn('Instance.new(', occlusion)
        debug = source('src/client/dev/HouseSocketDebugController.luau')
        self.assertIn('aim.CanQuery = false', debug)

    def test_standard_and_custom_characters_both_gate_aim_sockets(self):
        prompt = source('src/client/world/HouseSocketPromptController.luau')
        self.assertIn('if definition and definition.hoverRadius then 0 else radius(name)', prompt)
        self.assertIn('if definition and definition.hoverRadius then return end', prompt)
        self.assertIn('(not SpatialRoot.IsCustom(player) and not definition.hoverRadius)', prompt)
        self.assertIn('nearestCustomPrompt(root, not custom)', prompt)
        self.assertIn('nearestCustomPrompt(root, not SpatialRoot.IsCustom(player))', prompt)
        self.assertIn('remote:FireServer(socket, key)', prompt)

    def test_chest_has_two_debug_radii_and_spheres(self):
        ui = source('src/client/dev/HouseSocketDebugController.luau')
        self.assertIn('if spec.hoverRadius then 79 else 51', ui)
        self.assertIn('if spec.hoverRadius then\n                local useLabel', ui)
        self.assertIn('if spec.hoverRadius then\n                local aim = aimPreviews[socket]', ui)
        self.assertIn('SetTestHouseSocketHoverRadius', ui)
        self.assertIn('Game1SocketAimPreview', ui)
        self.assertIn('Game1SocketRadiusPreview', ui)

    def test_outside_aim_sphere_while_inside_use_fails(self):
        self.assertIsNone(ray_sphere_entry((0,0,0), (1,0,0), (6,5,0), 4))
        self.assertAlmostEqual(ray_sphere_entry((0,0,0), (1,0,0), (6,1,0), 4), 6-math.sqrt(15))

    def test_behind_camera_and_inside_facing_away_fail(self):
        self.assertIsNone(ray_sphere_entry((0,0,0), (1,0,0), (-10,0,0), 4))
        self.assertIsNone(ray_sphere_entry((0,0,0), (1,0,0), (-2,0,0), 4))
        self.assertIsNone(ray_sphere_entry((0,0,0), (1,0,0), (1,3,0), 5))
        self.assertAlmostEqual(ray_sphere_entry((0,0,0), (1,0,0), (2,0,0), 5), 2)

    def test_door_and_padlock_remain_non_aim(self):
        contract = source('src/shared/world/HouseSocketContract.luau')
        for line in contract.splitlines():
            if ('"door_01_handle_' in line or '"door_01_padlock_' in line):
                self.assertNotIn('hoverRadius',line)


if __name__ == '__main__':
    unittest.main()
