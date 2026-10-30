"""M166: independent read-only domain validators and negative contracts.

Fixture inputs are assembled from the checked-out project; mutation tests
intercept file reads rather than editing the user's files or databases.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "system/verify"))
from validators.actor_runtime import check_actor_runtime_contracts
from validators.combat_contact import check_combat_contact_contracts
from validators.monsters import MonsterSources, check_monster_contracts


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


class DomainValidatorM166Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.monster_inputs = {
            "schema_text": read("system/control-center/schema.sql"),
            "host_agent_text": read("system/control-center/host_agent.py") + "\n" + "\n".join(
                p.read_text(encoding="utf-8")
                for folder in ("api", "services")
                for p in (ROOT / "system/control-center" / folder).glob("*.py")
            ),
            "plugin_text": read("system/studio-plugin/Game1Bridge.server.luau") + "\n" + "\n".join(
                read(f"system/studio-plugin/modules/{name}") for name in (
                    "StudioModelLoadCommands.luau", "StudioActorSpawnCommands.luau", "StudioDebugPreferenceBridge.luau"
                )
            ),
            "ui": read("system/control-center/static/index.html"),
            "server_init_text": read("src/server/init.server.luau") + read("src/server/bootstrap/ServiceCatalog.luau"),
            "stats_config_text": read("src/shared/character/CharacterStatsConfig.luau"),
            "stats_service_text": read("src/server/character/CharacterStatsService.luau"),
            "animation_store_text": read("system/control-center/animation_store.py") + "\n" + "\n".join(
                p.read_text(encoding="utf-8")
                for p in sorted((ROOT / "system/control-center/animation_core").glob("*.py"))
            ),
        }
        cls.hitbox_inputs = {
            "damage_resolver_text": read("src/server/combat/AttackDamageResolver.luau"),
            "hitbox_implementation_text": "\n".join(read(f"src/server/combat/{name}.luau") for name in (
                "EntityHitboxService", "HitboxMeshGeometryCache", "HitboxDefinitionBuilder",
                "HitboxRuntimeFrames", "HitboxSpatialQueries"
            )),
        }

    def monsters(self, **overrides):
        errors = []
        inputs = {**self.monster_inputs, **overrides}
        result = check_monster_contracts(ROOT, errors.append, **inputs)
        self.assertIsInstance(result, MonsterSources)
        return errors, result

    def actors(self, sources: MonsterSources):
        errors = []
        check_actor_runtime_contracts(
            ROOT, errors.append, monster_attributes_text=sources.attributes_text,
            monster_runtime_text=sources.runtime_text,
        )
        return errors

    def contact(self, **overrides):
        errors = []
        check_combat_contact_contracts(ROOT, errors.append, **{**self.hitbox_inputs, **overrides})
        return errors

    def swap_read(self, relative: str, modifier):
        """Patch a single Path.read_text response; never alter source on disk."""
        path = ROOT / relative
        original = Path.read_text

        def intercepted(instance, *args, **kwargs):
            value = original(instance, *args, **kwargs)
            return modifier(value) if instance == path else value
        return patch.object(Path, "read_text", intercepted)

    def test_all_three_domains_accept_current_project(self):
        errors, sources = self.monsters()
        self.assertEqual(errors, [])
        self.assertIn("MonsterSpawnerService", sources.runtime_text)
        self.assertEqual(self.actors(sources), [])
        self.assertEqual(self.contact(), [])

    def test_monster_spawn_manifest_schema_diagnostic(self):
        with self.swap_read("assets/manifests/monster-spawns.json", lambda text:
                            json.dumps({**json.loads(text), "records": []})):
            errors, _ = self.monsters()
        self.assertIn("monster spawn manifest records must be an object", errors)

    def test_monster_store_missing_contract(self):
        with self.swap_read("system/control-center/monster_store.py",
                            lambda text: text.replace("class MonsterStore", "class RenamedMonsterStore")):
            errors, _ = self.monsters()
        self.assertIn("monster store missing class MonsterStore", errors)

    def test_monster_critical_stats_input_diagnostic(self):
        errors, _ = self.monsters(stats_config_text=self.monster_inputs["stats_config_text"].replace(
            "CritChance = 0", "CritChance = -1"))
        self.assertIn("character critical stat missing CritChance = 0", errors)

    def test_actor_input_guard_diagnostic(self):
        _, sources = self.monsters()
        with self.swap_read("src/client/UiInputGuard.luau", lambda text:
                            text.replace("GetFocusedTextBox", "OmittedFocusedTextBox")):
            errors = self.actors(sources)
        self.assertIn("global UI world-input guard missing GetFocusedTextBox", errors)

    def test_actor_options_runtime_diagnostic(self):
        _, sources = self.monsters()
        with self.swap_read("assets/manifests/options.json", lambda text:
                            json.dumps({**json.loads(text), "combat": {"stateDurationSeconds": 9.0}})):
            errors = self.actors(sources)
        self.assertIn("m26 combat state default duration must be 6 seconds", errors)

    def test_combat_headshot_reticle_contract(self):
        with self.swap_read("src/client/combat/AimPoseController.luau", lambda text:
                            text.replace("ViewportPointToRay", "ReticleRayRemoved")):
            errors = self.contact()
        self.assertIn("m33 center-screen aim-ray source missing ViewportPointToRay", errors)

    def test_combat_hitbox_and_contact_independent_inputs(self):
        errors = self.contact(hitbox_implementation_text=self.hitbox_inputs["hitbox_implementation_text"].replace(
            "rayBoxDistance", "NoRayBoxDistance"))
        self.assertIn("m33 finite aim-region ray query missing rayBoxDistance", errors)
        errors = self.contact(damage_resolver_text=self.hitbox_inputs["damage_resolver_text"].replace(
            "hitCount += 1", "hitCount = 0"))
        self.assertIn("m27 melee contact resolver must count each damageable target", errors)

    def test_validators_do_not_write_source_files(self):
        files = (ROOT / "assets/manifests/monsters.json", ROOT / "assets/manifests/options.json",
                 ROOT / "src/server/combat/AttackDamageResolver.luau")
        before = {p: p.read_bytes() for p in files}
        errors, sources = self.monsters()
        errors += self.actors(sources) + self.contact()
        self.assertEqual(errors, [])
        self.assertEqual(before, {p: p.read_bytes() for p in files})


if __name__ == "__main__":
    unittest.main()
