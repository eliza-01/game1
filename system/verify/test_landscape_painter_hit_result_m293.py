"""M293: surface and stem ray results must share one placement target shape.

RaycastResult is a Roblox engine userdata, not a Lua table; accessing
RaycastResult.kind or RaycastResult.stem throws rather than returning nil.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
PLACEMENT = ROOT / "system/landscape-plugin/modules/LandscapeAssetPlacement.luau"
STEM = ROOT / "system/landscape-plugin/modules/LandscapeStemTarget.luau"


class LandscapePainterHitResultM293(unittest.TestCase):
    def test_surface_is_normalized_before_cursor_access(self):
        source = PLACEMENT.read_text(encoding="utf-8")
        resolver = source.split("function Placement:ResolveHit()", 1)[1].split("\nend", 1)[0]
        self.assertIn("local surface = Surface.Raycast(", resolver)
        self.assertRegex(resolver, r"local surfaceTarget = if surface then \{")
        self.assertIn("Position = surface.Position", resolver)
        self.assertIn("Normal = surface.Normal", resolver)
        self.assertIn('kind = "surface"', resolver)
        self.assertIn('if self.targetMode == "surface" then return surfaceTarget', resolver)
        self.assertRegex(resolver, r"return surfaceTarget\s*$")
        # StemTarget.Find must still see the original RaycastResult so
        # occlusion distance remains correct when a stem lies behind a wall.
        self.assertIn("self.mouse.UnitRay, surface, RAY_LENGTH", resolver)

    def test_all_cursor_fields_come_from_normalized_target_records(self):
        source = PLACEMENT.read_text(encoding="utf-8")
        resolver = source.split("function Placement:ResolveHit()", 1)[1].split("\nend", 1)[0]
        self.assertNotRegex(resolver, r"\bsurface\.(?:kind|stem|branch)\b")
        self.assertIn('kind = hit.kind or "surface", stem = hit.stem, branch = hit.branch', source)
        self.assertIn("local hit = self:ResolveHit()", source)
        stem = STEM.read_text(encoding="utf-8")
        self.assertIn('kind = "stem", stem = part, branch = branch', stem)


if __name__ == "__main__":
    unittest.main()
