"""M74 contract tests: clip overrides must be safe and reversible."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "system/control-center"))
from animation_speed_scaling_store import AnimationSpeedScalingStore


class CustomScalingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="m74-custom-")
        self.root = Path(self.temp.name)
        for name in ("character-animations.json", "npc-animations.json", "monster-animations.json"):
            target = self.root / "assets/manifests" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / "assets/manifests" / name, target)
        self.store = AnimationSpeedScalingStore(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_publication_catalog_searchable_and_all_kinds(self):
        rows = self.store.snapshot()["catalog"]
        self.assertTrue({"character", "npc", "monster"}.issubset({r["kind"] for r in rows}))
        self.assertEqual(len(rows), len({r["assetId"] for r in rows}))
        self.assertTrue(all(row["assetId"].isdigit() for row in rows))

    def test_override_and_remove_preserves_default_profiles_and_ids(self):
        before = self.store.snapshot()
        clip = next(r for r in before["catalog"] if r["kind"] == "npc")
        saved = self.store.save_custom({"assetId": clip["assetId"], "stat": "AttackSpeed", "unitsPerPercent": 3.75})
        self.assertEqual(saved["customScaling"][0]["unitsPerPercent"], 3.75)
        self.assertEqual(before["profiles"], saved["profiles"])
        registry = self.store.registry_path.read_text(encoding="utf8")
        self.assertIn('custom = table.freeze({', registry)
        self.assertIn(clip["assetId"], registry)
        removed = self.store.save_custom({"assetId": clip["assetId"], "delete": True})
        self.assertEqual(removed["customScaling"], [])
        self.assertEqual(removed["profiles"], before["profiles"])

    def test_rejects_bad_asset_id_units_and_stat(self):
        clip = self.store.catalog()[0]
        for patch in (
            {"assetId": "9999999999999999", "stat": "RunSpeed", "unitsPerPercent": 1},
            {"assetId": clip["assetId"], "stat": "UnknownStat", "unitsPerPercent": 1},
            {"assetId": clip["assetId"], "stat": "RunSpeed", "unitsPerPercent": 0},
            {"assetId": clip["assetId"], "stat": "RunSpeed", "unitsPerPercent": 1001},
        ):
            with self.assertRaises(ValueError):
                self.store.save_custom(patch)

    def test_runtime_debug_safe_and_no_frame_polling(self):
        scaling = (ROOT / "src/shared/animation/AnimationSpeedScaling.luau").read_text()
        studio = (ROOT / "src/server/dev/CustomScalingDebugService.luau").read_text()
        client = (ROOT / "src/client/dev/CustomScalingDebugController.luau").read_text()
        npc = (ROOT / "src/server/npc/NpcAnimationTracks.luau").read_text()
        for token in ("RuleForAnimation", "ResolveForAnimation", "RefreshPlaying", "Policy.CustomRule"):
            self.assertIn(token, scaling)
        self.assertIn("Registry.custom", (ROOT / "src/shared/animation/AnimationScalingPolicy.luau").read_text())
        self.assertIn("RunService:IsStudio()", studio)
        self.assertIn("GetPlayingAnimationTracks", scaling)
        self.assertIn("RunService:IsStudio()", client)
        movement = (ROOT / "src/server/npc/NpcCombatAIService.luau").read_text()
        self.assertIn('NpcAttackPursuitAnimationId', movement)
        self.assertIn('AnimationSpeedScaling.ResolveForAnimation(', movement)
        self.assertIn('speedPercentOverride or AnimationSpeedScaling.ResolveForModel', npc)


if __name__ == "__main__":
    unittest.main()
