"""M165: deterministic checks for project identity and runtime layout."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "system/verify"))
from validators.project_layout import (
    LEGACY_RUNTIME_MODULES,
    REQUIRED_RUNTIME_MODULES,
    check_project_identity,
    check_project_layout,
)


class ProjectLayoutValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="game1-m165-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "game1"
        self.project = {
            "name": "game1", "tree": {
                "ReplicatedStorage": {"Game1Shared": {}},
                "ServerScriptService": {"Game1Server": {}},
                "StarterPlayer": {"StarterPlayerScripts": {"Game1Client": {}}},
            },
        }
        self.config = {
            "name": "game1", "slug": "game1", "namespaces": {
                "shared": "Game1Shared", "server": "Game1Server",
                "client": "Game1Client", "remotes": "Game1Remotes",
            },
            "ports": {"rojo": 34882},
        }
        self.write_json("default.project.json", self.project)
        self.write_json("config/project.json", self.config)
        for path in REQUIRED_RUNTIME_MODULES:
            self.write(path, "-- valid stub\n")

    def write(self, path: str, content: str) -> Path:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def write_json(self, path: str, obj: object) -> Path:
        return self.write(path, json.dumps(obj))

    def check(self) -> list[str]:
        messages: list[str] = []
        check_project_identity(self.root, messages.append)
        check_project_layout(self.root, messages.append)
        return messages

    def test_clean_fixture_has_no_errors(self):
        self.assertEqual(self.check(), [])

    def test_project_identity_and_namespace_errors_keep_order(self):
        self.project["name"] = "other"
        del self.project["tree"]["ReplicatedStorage"]["Game1Shared"]
        del self.project["tree"]["StarterPlayer"]["StarterPlayerScripts"]["Game1Client"]
        self.write_json("default.project.json", self.project)
        self.assertEqual(self.check(), [
            "default.project.json project name must be game1",
            "Game1Shared namespace missing",
            "Game1Client namespace missing",
        ])

    def test_malformed_rojo_tree_still_reports_one_error(self):
        self.project["tree"] = []
        self.write_json("default.project.json", self.project)
        self.assertEqual(self.check(), ["default.project.json namespace tree is malformed"])

    def test_legacy_project_root_name_is_forbidden(self):
        new_root = self.root.with_name("robloxlineage-copy")
        self.root.rename(new_root)
        self.root = new_root
        self.assertEqual(self.check(), ["game1 root is inside/a descendant of a robloxlineage path"])

    def test_place_and_legacy_runtime_files_are_reported(self):
        self.write("place/current.rbxl", "not a real Roblox place")
        legacy = LEGACY_RUNTIME_MODULES[0]
        self.write(legacy, "-- obsolete")
        self.assertEqual(self.check(), [
            "place/current.rbxl is forbidden in game1; canonical file is place/game1.rbxl",
            f"legacy flat runtime module must be removed: {legacy}",
        ])

    def test_forbidden_tokens_in_scanned_extensions_keep_order(self):
        self.write("src/client/check.luau", "RobloxLineageShared\nCombatV2\n")
        self.write("system/control-center/ignored.txt", "NewPlaceShared")
        self.assertEqual(self.check(), [
            "src/client/check.luau contains forbidden token RobloxLineageShared",
            "src/client/check.luau contains forbidden token CombatV2",
        ])

    def test_config_namespace_and_port_collisions(self):
        self.config["name"] = "other"
        self.config["namespaces"]["shared"] = "wrong"
        self.config["ports"] = {"rojo": 43720}
        self.write_json("config/project.json", self.config)
        self.assertEqual(self.check(), [
            "config/project.json identity must be game1",
            "config/project.json namespaces do not match game1 contract",
            "port collision with robloxlineage baseline",
            "game1 rojo port must be 34882",
        ])

    def test_missing_required_runtime_module(self):
        missing = REQUIRED_RUNTIME_MODULES[10]
        (self.root / missing).unlink()
        self.assertEqual(self.check(), [f"runtime module missing: {missing}"])

    def test_all_missing_runtime_reports_in_stable_order(self):
        for relative in REQUIRED_RUNTIME_MODULES:
            (self.root / relative).unlink()
        self.assertEqual(self.check(), [
            f"runtime module missing: {relative}" for relative in REQUIRED_RUNTIME_MODULES
        ])

    def test_validator_never_writes_source_or_manifests(self):
        observed = [self.root / "default.project.json", self.root / "config/project.json"]
        before = [p.read_bytes() for p in observed]
        self.assertEqual(self.check(), [])
        self.assertEqual([p.read_bytes() for p in observed], before)
        self.assertFalse((self.root / "assets").exists())
        self.assertFalse((self.root / ".control-center").exists())


if __name__ == "__main__":
    unittest.main()
