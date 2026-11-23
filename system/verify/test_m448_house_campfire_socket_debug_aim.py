"""M448: House + Campfire Studio debug; reticle-and-reach information gating.

Pure geometry checks mirror the public ray/sphere contract. Roblox Play must
still verify camera/occlusion and populated placement discovery.
"""
from pathlib import Path
import math
import unittest

ROOT = Path(__file__).resolve().parents[2]
def src(path): return (ROOT / path).read_text(encoding='utf-8')


def ray_entry(origin, direction, center, radius):
    if radius <= 0: return None
    delta = tuple(c-o for c,o in zip(center, origin))
    forward = sum(a*b for a,b in zip(delta, direction))
    if forward < -radius: return None
    nearest = tuple(o + d*max(0,forward) for o,d in zip(origin,direction))
    side = sum((c-n)**2 for c,n in zip(center,nearest))
    if side > radius*radius: return None
    length = math.sqrt(sum(d*d for d in delta))
    if length < radius:
        core = min(radius*.5, 2)
        return forward if forward > 0 and side <= core*core else None
    return max(0, forward-math.sqrt(max(0,radius*radius-side)))


def info_is_visible(avatar, socket, use_radius, info_radius, ray_hit, has_los):
    distance = math.dist(avatar, socket)
    return distance <= min(use_radius, info_radius) and ray_hit is not None and has_los


class SocketDebugM448(unittest.TestCase):
    def test_information_requires_both_distance_and_aim_and_line_of_sight(self):
        eye = (0., 2., 0.)
        socket = (6., 2., 0.)
        on_target = ray_entry(eye, (1., 0., 0.), socket, 4)
        away = ray_entry(eye, (0., 0., 1.), socket, 4)
        self.assertIsNotNone(on_target)
        self.assertIsNone(away)
        self.assertTrue(info_is_visible((0,0,0), socket, 8, 50, on_target, True))
        self.assertFalse(info_is_visible((0,0,0), socket, 8, 50, away, True))
        self.assertFalse(info_is_visible((0,0,0), socket, 8, 50, on_target, False))
        self.assertFalse(info_is_visible((-12,0,0), socket, 8, 50, on_target, True))
        self.assertFalse(info_is_visible((0,0,0), socket, 8, 2, on_target, True))

    def test_house_fireplace_has_independent_use_and_aim(self):
        contract = src('src/shared/world/HouseSocketContract.luau')
        self.assertIn('"fireplace_01_socket", role = "fireplace", action = "Разжечь огонь", radius = 8, hoverRadius = 4', contract)
        server = src('src/server/world/HouseSocketService.luau')
        self.assertIn('radiusFor(player, name) + (if definition.hoverRadius then 0 else 2)', server)

    def test_campfire_has_separate_authority_and_read_only_mount(self):
        contract = src('src/shared/world/CampfireSocketContract.luau')
        self.assertIn('Config.CampfireInteractionRadius', contract)
        self.assertIn('Config.CampfireAimRadius', contract)
        self.assertIn('name = "cooking_pot_01_socket", role = "pot_mount"', contract)
        self.assertIn('radius = 0, interact = false', contract)
        house = src('src/shared/world/HouseSocketContract.luau')
        self.assertNotIn('"fire_socket"', house)
        self.assertNotIn('"cooking_pot_01_socket"', house)

    def test_campfire_debug_is_studio_authorized_and_no_world_rescan(self):
        server = src('src/server/world/LocationCampfireService.luau')
        debug = src('src/server/dev/HouseSocketDebugService.luau')
        self.assertIn('function Service.GetDebugStatus(player: Player)', server)
        self.assertIn('for model, entry in pairs(registered) do', server)
        self.assertNotIn('Workspace:GetDescendants()', server)
        self.assertIn('RunService:IsStudio()', server)
        self.assertIn('PublishedDebugAccess.ServerAllowed(player)', server)
        for remote in ('GetTestCampfireSockets', 'SetTestCampfireSocketRadius', 'SetTestCampfireSocketHoverRadius'):
            self.assertIn(remote, debug)
        self.assertIn('Campfire.RadiusAttribute("fire_socket")', src('src/client/world/HouseSocketPromptController.luau').replace('CampfireContract.', 'Campfire.'))
        self.assertIn('useRadius(player)', server)

    def test_previews_do_not_interfere_with_world_raycast(self):
        client = src('src/client/dev/HouseSocketDebugController.luau')
        for marker in ('Game1SocketRadiusPreview', 'Game1SocketAimPreview',
                       '"Game1DecoAssetSlug") == "campfire_01"',
                       'SetTestCampfireSocketRadius', 'SetTestCampfireSocketHoverRadius',
                       'CampfireContract.Get(socket.Name)', 'role == "pot_mount"',
                       'table.sort(options,', 'CanQuery = false', 'CanCollide = false', 'CanTouch = false'):
            self.assertIn(marker, client)
        self.assertNotIn('Workspace:GetDescendants()', src('src/server/world/LocationCampfireService.luau'))

    def test_status_renders_even_when_no_action_offered(self):
        client = src('src/client/world/HouseFireplaceController.luau')
        self.assertIn('Aim.RaySphereEntry(', client)
        self.assertIn('Occlusion.IsClear(', client)
        self.assertIn('CameraController.CursorPoint()', client)
        self.assertIn('distance > math.min(visibleRadius, useRadius)', client)
        self.assertIn('elseif registered(socket) and ray and hoverRadius > 0 then', client)
        self.assertNotIn('prompt.Enabled', client)
        self.assertIn('dock:Present("fireplace", nil, "", false)', client)
        self.assertIn('dock:Forget(socket)', client)
        self.assertIn('collapsed[currentSource] = true', src('src/client/world/InformativeWindowDock.luau'))


if __name__ == '__main__': unittest.main()
