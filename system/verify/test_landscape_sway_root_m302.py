"""M302: client lantern scan must support Game1's custom character root."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


class LandscapeSwayRootM302(unittest.TestCase):
    def test_lookup_uses_actual_game1_root(self):
        character_rig = (ROOT / 'src/server/character/CharacterRigService.luau').read_text(encoding='utf-8')
        camera = (ROOT / 'src/client/character/CameraController.luau').read_text(encoding='utf-8')
        sway = (ROOT / 'src/client/world/LandscapeSwayController.luau').read_text(encoding='utf-8')
        self.assertIn('root.Name = "RootCollider"', character_rig)
        self.assertIn('newCharacter:WaitForChild("RootCollider", 10)', camera)
        self.assertIn('local function viewerPosition(): Vector3?', sway)
        lookup = sway[sway.index('local function viewerPosition()'):sway.index('local function near(')]
        self.assertLess(lookup.index('FindFirstChild("RootCollider")'), lookup.index('FindFirstChild("HumanoidRootPart")'))
        self.assertIn('root:IsA("BasePart")', lookup)
        self.assertIn('return if root and root:IsA("BasePart") then root.Position else nil', lookup)

    def test_all_distance_gates_share_the_same_resolver(self):
        sway = (ROOT / 'src/client/world/LandscapeSwayController.luau').read_text(encoding='utf-8')
        tick = sway[sway.index('local function tickSway()'):sway.index('local function ensureRunning()')]
        scan = sway[sway.index('local function scanNearby()'):sway.index('local function impact(')]
        impact = sway[sway.index('local function impact('):sway.index('local function wind(')]
        self.assertIn('local position = viewerPosition()', tick)
        self.assertIn('not near(model, position)', tick)
        self.assertIn('local position = viewerPosition()', scan)
        self.assertIn('if not folder or not position then return end', scan)
        self.assertIn('(position - item:GetPivot().Position).Magnitude', scan)
        self.assertIn('near(model, viewerPosition())', impact)
        # No separate humanoid-only gate may silently disable the animation.
        self.assertEqual(len(re.findall(r'FindFirstChild\("HumanoidRootPart"\)', sway)), 1)
        self.assertIn('Config.AmbientMaxTargets', scan)
        self.assertIn('model:PivotTo(frame)', tick)


if __name__ == '__main__':
    unittest.main()
