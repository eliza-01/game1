from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET
from diagnostic_payloads import require_payloads

ROOT = Path(__file__).resolve().parents[2]
def read(path):
    return (ROOT / path).read_text(encoding='utf-8')

class M600(unittest.TestCase):
    def test_runtime_raster_payload(self):
        data = read('src/client/world/HouseInteractionIconData.luau')
        for state in ['LockClosed', 'LockOpen', 'DoorClosed', 'DoorOpen']:
            raw = re.search(rf'{state} = "([0-9a-f]+)"', data)[1]
            self.assertEqual(len(raw) % 12, 0)
            self.assertEqual(sum(int(raw[i:i+4],16) for i in range(0,len(raw),12)),48*48)
    def test_svg_raster_payload(self):
        states = ['LockClosed', 'LockOpen', 'DoorClosed', 'DoorOpen']
        require_payloads(self, ROOT, [f'assets/ui/house-interaction/{state}.{ext}' for state in states for ext in ('svg', 'png')])
        for state in states:
            self.assertEqual(ET.parse(ROOT / f'assets/ui/house-interaction/{state}.svg').getroot().tag, '{http://www.w3.org/2000/svg}svg')
            self.assertEqual((ROOT / f'assets/ui/house-interaction/{state}.png').read_bytes()[:8], b'\x89PNG\r\n\x1a\n')
    def test_range_gated_door_mesh_and_activation(self):
        hud = read('src/client/world/HouseSocketPromptController.luau')
        self.assertLess(hud.index('if distance > maxDistance then continue end'), hud.index('doors[door] = true'))
        self.assertIn('table.find(availableActions(socket, selected), matching)', hud)
        ray = read('src/client/world/DoorInteractionRaycast.luau')
        self.assertLess(ray.index('if next(doors) == nil'), ray.index('Workspace:Raycast('))
        self.assertEqual(ray.count('Workspace:Raycast('),1)
        self.assertIn('for _, part in changed do part.CanQuery = false end', ray)
        self.assertIn('DoorRaycast.Bind(proxy, part)', read('src/client/world/HouseVisualAdapter.luau'))
    def test_authority_and_icons(self):
        server = read('src/server/world/HouseSocketService.luau')
        for state in ['LockClosed', 'LockOpen', 'DoorOpen', 'DoorClosed']:
            self.assertIn(f'"{state}"', server)
        self.assertIn('if definition.role == "door" and key == "E" then return end', server)
        self.assertIn('if definition.role == "door" and key == "E" then allowedDistance = radiusFor(player, name) end', server)
        self.assertIn('cooldown[player] = now', server)
    def test_npc_format_only(self):
        hud = read('src/client/combat/HealthBarView.luau')
        self.assertIn('return NpcDisplayNameFormatter.Format(text)', hud)
        self.assertIn('model:GetAttribute("Game1NpcRuntime") == true or model:GetAttribute("NpcSlug") ~= nil', hud)
        self.assertIn('gsub("%d+", "")', read('src/client/combat/NpcDisplayNameFormatter.luau'))
