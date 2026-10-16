"""M96 boundaries, API compatibility and optional execution of pure Luau arithmetic."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCALE = ROOT / "src/shared/animation"


class AnimationScalingM96(unittest.TestCase):
    def test_public_api_remains_stable(self):
        facade = (SCALE / "AnimationSpeedScaling.luau").read_text(encoding="utf-8")
        for method in (
            "DebugUnitsPerPercentAttribute", "TargetForModel", "Rule", "ResolvePercent",
            "AssetId", "Catalog", "RuleForAnimation", "ResolveDetailsForModel",
            "ResolveForModel", "ResolveForModelWithStatValue", "ResolveScaleForModel",
            "ResolveForAnimation", "ResolveScaleForAnimation", "RefreshPlaying",
        ):
            with self.subTest(method=method):
                self.assertIn(f"function AnimationSpeedScaling.{method}(", facade)
        for constant in (
            "MinPercent", "MaxPercent", "MinUnitsPerPercent", "MaxUnitsPerPercent",
            "CustomDebugPrefix", "DebugUnitsPerPercentPrefix",
        ):
            self.assertIn(f"AnimationSpeedScaling.{constant} =", facade)
        for name in ("AnimationScalingFormula", "AnimationScalingPolicy", "AnimationScalingDebugOverrides"):
            self.assertIn(f'WaitForChild("{name}")', facade)
        self.assertIn("GetPlayingAnimationTracks", facade)
        self.assertNotIn('game:GetService("Workspace")', facade)

    def test_ownership_and_precedence(self):
        math = (SCALE / "AnimationScalingFormula.luau").read_text(encoding="utf-8")
        policy = (SCALE / "AnimationScalingPolicy.luau").read_text(encoding="utf-8")
        overrides = (SCALE / "AnimationScalingDebugOverrides.luau").read_text(encoding="utf-8")
        facade = (SCALE / "AnimationSpeedScaling.luau").read_text(encoding="utf-8")
        self.assertNotIn("game:", math)
        self.assertNotIn("GetAttribute", math)
        self.assertNotIn("Registry", math)
        self.assertNotIn("game:GetService", policy)
        self.assertNotIn("Workspace:GetAttribute", policy)
        self.assertNotIn("Workspace:GetAttribute", facade)
        self.assertNotIn("Registry", overrides)
        self.assertIn('if not (typeof(debugUnits) == "number" and debugUnits > 0)', overrides)
        # Workspace debug rule must override published custom clip, then profile fallback.
        self.assertLess(facade.index("if debugRule then"), facade.index("if authored then"))
        self.assertLess(facade.index("if authored then"), facade.index("return AnimationSpeedScaling.Rule(targetType"))
        # A custom clip ignores stat overrides AND model-channel debug units (legacy contract).
        self.assertIn("statValueOverride ~= nil and not isCustom", facade)
        self.assertIn("debugUnitsPerPercent ~= nil and not isCustom", facade)

    def test_pure_formula_runtime_if_lua_is_available(self):
        # Formula intentionally uses the Lua 5.3 subset of Luau. This optional
        # runtime check executes the production .luau file, not a Python rewrite.
        lua = shutil.which("luatex")
        if not lua:
            self.skipTest("luatex absent; pure Luau formula contract checked structurally")
        module = str((SCALE / "AnimationScalingFormula.luau").resolve()).replace("\\", "/")
        script = f'''table.freeze = function(t) return t end
math.clamp = function(v, lower, upper) return math.min(upper, math.max(lower, v)) end
local f = dofile({module!r})
local function eq(actual, expected)
    assert(actual == expected, tostring(actual) .. " != " .. tostring(expected))
end
-- Baseline M95 formula behavior and boundary cases.
eq(f.RulePercent(200, 2), 100)
eq(f.RulePercent(-1, 2), 1)
eq(f.RulePercent(9999, 2), 400)
eq(f.RulePercent(1, 0), 400)
eq(f.RulePercent(1000, math.huge), 400)
eq(f.RulePercent("NaN", 2), 1)
eq(f.DetailsPercent(300, f.AuthoredUnits(2)), 150)
eq(f.DetailsPercent(300, f.DebugUnits(6, 2)), 50)
eq(f.DebugUnits("invalid", 4), 4)
eq(f.AuthoredUnits(1e9), 1000)
eq(f.AuthoredUnits(-20), 0.001)
eq(f.Finite(0/0, 12), 12)
eq(f.Finite(math.huge, 12), 12)
'''
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "test_m96_scaling.lua"
            file.write_text(script, encoding="utf-8")
            proc = subprocess.run([lua, "--luaonly", str(file)], capture_output=True, text=True, timeout=15)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
