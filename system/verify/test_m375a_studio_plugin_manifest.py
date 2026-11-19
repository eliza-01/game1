"""M375a: Rojo manifest completeness must be checked before Studio installation."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from validators.studio_plugin_manifest import check_studio_plugin_manifest


ROOT = Path(__file__).resolve().parents[2]


class StudioPluginManifestM375a(unittest.TestCase):
    def test_real_project_contains_every_local_module(self):
        errors = []
        check_studio_plugin_manifest(ROOT, errors.append)
        self.assertEqual(errors, [])
        project = json.loads(
            (ROOT / "system/studio-plugin/plugin.project.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            project["tree"]["modules"]["StudioRealEstateAppearance"]["$path"],
            "modules/StudioRealEstateAppearance.luau",
        )

    def test_unlisted_module_is_rejected_before_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            plugin = Path(tmp) / "system/studio-plugin"
            modules = plugin / "modules"
            modules.mkdir(parents=True)
            (modules / "Example.luau").write_text("return {}", encoding="utf-8")
            (plugin / "plugin.project.json").write_text(
                json.dumps({"tree": {"modules": {"$className": "Folder"}}}),
                encoding="utf-8",
            )
            errors = []
            check_studio_plugin_manifest(Path(tmp), errors.append)
            self.assertTrue(any("Example.luau" in issue for issue in errors), errors)

    def test_nonexistent_declared_module_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            plugin = Path(tmp) / "system/studio-plugin"
            (plugin / "modules").mkdir(parents=True)
            (plugin / "plugin.project.json").write_text(
                json.dumps({"tree": {"modules": {"Missing": {"$path": "modules/Missing.luau"}}}}),
                encoding="utf-8",
            )
            errors = []
            check_studio_plugin_manifest(Path(tmp), errors.append)
            self.assertTrue(any("Missing" in issue for issue in errors), errors)


if __name__ == "__main__":
    unittest.main()
