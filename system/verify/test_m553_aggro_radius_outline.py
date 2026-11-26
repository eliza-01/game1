"""AG visual toggle independence, outline-only geometry and cleanup."""
from pathlib import Path
import math
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / 'src/client/dev/GameplayAggroController.luau').read_text(encoding='utf8')


class AggroOutline(unittest.TestCase):
    def test_default_visibility_independent_of_panel(self):
        self.assertIn('local show=true', SOURCE)
        self.assertIn('show=not show', SOURCE)
        update = SOURCE.split('local connection=RunService.Heartbeat:Connect', 1)[1]
        self.assertNotIn('panel.Visible', update)
        for token in ('if not show or not zone', 'zone<1 or zone>6', 'Game1GameplayTestActive', 'Game1GameplayTestOwner', '==zone', '=="Alive"', 'e.radius>0'):
            self.assertIn(token, update)

    def test_outline_geometry(self):
        self.assertNotIn('Enum.PartType.Cylinder', SOURCE)
        count = int(re.search(r'RING_SEGMENTS=(\d+)', SOURCE)[1])
        height = float(re.search(r'RING_HEIGHT=([.\d]+)', SOURCE)[1])
        width = float(re.search(r'RING_WIDTH=([.\d]+)', SOURCE)[1])
        self.assertGreaterEqual(count, 64)
        self.assertLessEqual(height, .3)
        self.assertLessEqual(width, .15)
        self.assertIn('radius*math.cos(halfAngle)', SOURCE)
        self.assertIn('2*radius*math.sin(halfAngle)', SOURCE)
        for radius in (1, 20, 24, 60, 10000):
            half = math.pi/count
            apothem = radius*math.cos(half)
            chord = 2*radius*math.sin(half)
            self.assertAlmostEqual(math.hypot(apothem, chord/2), radius)
            self.assertLess(chord, 2048)

    def test_local_noninteractive_and_cached(self):
        for token in ('CanCollide=false', 'CanTouch=false', 'CanQuery=false', 'CastShadow=false', 'if ring.radius~=radius', 'if ring.aggressive~=aggressive', 'if ring.center~=center', 'ring.model:PivotTo', 'ring.model:Destroy()', 'connection:Disconnect(); clear()'):
            self.assertIn(token, SOURCE)
        self.assertIn('Color3.fromRGB(239,70,70)', SOURCE)
        self.assertIn('Color3.fromRGB(145,155,165)', SOURCE)


if __name__ == '__main__':
    unittest.main()
