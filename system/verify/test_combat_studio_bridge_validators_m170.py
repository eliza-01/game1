"""M170 behavior-preserving Combat/Hitbox/Studio/Timeline extraction tests.

Deliberately broken inputs are intercepted in memory; no project file is edited.
"""
from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "system/verify"))

from validators.combat_foundation import check_combat_foundation
from validators.hitbox_runtime import check_hitbox_runtime
from validators.studio_character_bridge import check_studio_character_bridge
from validators.registered_attack_clips import check_registered_attack_clips


class CoreContractsM170Tests(unittest.TestCase):
    def intercept(self, relative: str, change):
        """Override one source read without modifying files on disk."""
        path = ROOT / relative
        original = Path.read_text

        def replacement(instance, *args, **kwargs):
            content = original(instance, *args, **kwargs)
            return change(content) if instance == path else content

        return patch.object(Path, "read_text", replacement)

    def combat(self):
        problems = []
        sources = check_combat_foundation(ROOT, problems.append)
        return problems, sources

    def hitbox(self):
        problems = []
        sources = check_hitbox_runtime(ROOT, problems.append)
        return problems, sources

    def bridge(self):
        problems = []
        sources = check_studio_character_bridge(ROOT, problems.append)
        return problems, sources

    def clips(self, timeline=None):
        problems = []
        if timeline is None:
            timeline = (ROOT / "src/shared/combat/AttackTimelineData.luau").read_text(encoding="utf-8")
        check_registered_attack_clips(ROOT, problems.append, attack_timeline_data_text=timeline)
        return problems

    def test_current_combat_passes_and_returns_shared_sources(self):
        problems, sources = self.combat()
        self.assertEqual(problems, [])
        self.assertEqual(len(sources), 4)
        self.assertIn("AttackSessionStore.IsCoolingDown", sources.attack_text)
        self.assertIn("AttackTimelineConfig.ResolveRuntime", sources.attack_timeline_text)

    def test_missing_critical_multiplier_reports_original_error(self):
        with self.intercept("src/server/combat/DamageService.luau", lambda s: s.replace(
                "CRITICAL_DAMAGE_MULTIPLIER = 2", "CRITICAL_DAMAGE_MULTIPLIER = 9")):
            problems, _ = self.combat()
        self.assertIn("critical damage contract missing CRITICAL_DAMAGE_MULTIPLIER = 2", problems)

    def test_combat_contracts_keep_diagnostic_order(self):
        with self.intercept("src/server/combat/AttackService.luau", lambda s: s.replace(
                "[game1][attack] miss", "[game1][attack] removed").replace(
                "AttackSessionStore.IsCoolingDown", "AttackSessionStore.Disabled")):
            problems, _ = self.combat()
        self.assertEqual(problems, [
            "attack smoke-test logging contract missing",
            "server attack timeline contract missing AttackSessionStore.IsCoolingDown",
        ])

    def test_bad_timeline_runtime_fields_detected(self):
        with self.intercept("src/shared/combat/AttackTimelineConfig.luau", lambda s: s + "\nResultTypes\n"):
            problems, _ = self.combat()
        self.assertIn("obsolete attack timeline runtime field remains: ResultTypes", problems)

    def test_hitbox_valid_source_and_result(self):
        problems, sources = self.hitbox()
        self.assertEqual(problems, [])
        self.assertIn("HitboxSpatialQueries.AimContact", sources)

    def test_hitbox_missing_delegate_is_detected(self):
        with self.intercept("src/server/combat/EntityHitboxService.luau", lambda s: s.replace(
                "HitboxMeshGeometryCache.Read(meshPart)", "NoGeometryCacheRead(meshPart)")):
            problems, _ = self.hitbox()
        self.assertIn("m99 hitbox facade missing delegation HitboxMeshGeometryCache.Read(meshPart)", problems)

    def test_hitbox_forbidden_legacy_path_is_detected(self):
        with self.intercept("src/server/combat/EntityHitboxService.luau", lambda s: s + "\n-- root_fallback\n"):
            problems, _ = self.hitbox()
        self.assertIn("obsolete combat-hitbox runtime remains: root_fallback", problems)

    def test_headshot_resolver_bone_requirement(self):
        with self.intercept("src/shared/combat/SkeletonHeadResolver.luau", lambda s: s.replace(
                'token == "face"', 'token == "ear"')):
            problems, _ = self.hitbox()
        self.assertIn('head-bone resolver missing token == "face"', problems)

    def test_studio_bridge_source_and_result(self):
        problems, (plugin, host) = self.bridge()
        self.assertEqual(problems, [])
        self.assertIn('BRIDGE_URL = "http://127.0.0.1:43137"', plugin)
        self.assertIn('sync_suffix = "/sync"', host)

    def test_studio_bridge_rejects_authored_basis_correction(self):
        with self.intercept("system/studio-plugin/modules/CharacterTemplate.luau", lambda s: s + "\n-- normalizeSkeletonOrientation\n"):
            problems, _ = self.bridge()
        self.assertIn("Studio rig sync must preserve authored FBX basis; forbidden orientation correction remains: normalizeSkeletonOrientation", problems)

    def test_studio_bridge_rejects_removed_model_load(self):
        with self.intercept("system/control-center/studio_bridge.py", lambda s: s.replace(
                "run_model_load_bridge", "removed_model_load_bridge")):
            problems, _ = self.bridge()
        self.assertIn("reference-style Studio model load bridge is missing", problems)

    def test_timeline_coverage_passes_and_rejects_missing_clip(self):
        self.assertEqual(self.clips(), [])
        original = (ROOT / "src/shared/combat/AttackTimelineData.luau").read_text(encoding="utf-8")
        self.assertIn('["human_female__weapon__1hs__attack__01"]', original)
        problems = self.clips(original.replace('["human_female__weapon__1hs__attack__01"]', '["missing_clip"]'))
        self.assertIn("registered attack clip has no authoritative timeline: human_female__weapon__1hs__attack__01", problems)

    def test_all_four_are_read_only(self):
        paths = (
            ROOT / "assets/manifests/character-animations.json",
            ROOT / "assets/manifests/monster-animations.json",
            ROOT / "src/server/combat/EntityHitboxService.luau",
            ROOT / "system/studio-plugin/modules/CharacterTemplate.luau",
        )
        before = [p.read_bytes() for p in paths]
        self.assertEqual(self.combat()[0], [])
        self.assertEqual(self.hitbox()[0], [])
        self.assertEqual(self.bridge()[0], [])
        self.assertEqual(self.clips(), [])
        self.assertEqual(before, [p.read_bytes() for p in paths])


if __name__ == "__main__":
    unittest.main()
