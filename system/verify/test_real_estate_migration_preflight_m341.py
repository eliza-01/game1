"""M341 contract tests: read-only inventory + behavior-preserving rig role extraction."""
from __future__ import annotations

import importlib.util
import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "system/studio-plugin"
AUDIT = ROOT / "system/verify/m341_real_estate_preflight.py"
spec = importlib.util.spec_from_file_location("m341_preflight", AUDIT)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


class RealEstatePreflightM341(unittest.TestCase):
    def fixture(self, folder: Path):
        db = folder / ".control-center/game1_real_estate.db"
        db.parent.mkdir(parents=True)
        with closing(sqlite3.connect(db)) as c, c:
            c.execute("CREATE TABLE real_estate(slug TEXT, skeleton_json TEXT, mesh_options_json TEXT, model_rigs_json TEXT)")
            c.execute("INSERT INTO real_estate VALUES(?,?,?,?)", (
                "house_test", json.dumps({"meshes": [
                    {"name":"house","vertices":1234}, {"name":"col_mesh","vertices":321},
                    {"name":"door","vertices":90}]}),
                json.dumps({"house":{"noCollide":True},"col_mesh":{"noCollide":False,"collisionFidelity":"PreciseConvexDecomposition"},"door":{"noCollide":False}}),
                json.dumps({"house":42,"col_mesh":43,"door":44})))
        manifest = folder / "assets/manifests/real-estate-placements.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({"schemaVersion":1,"plotCount":50,"items":[
            {"houseSlug":"house_test", "plotIndex":1,"houseAnchorLocalCFrame":None},
            {"houseSlug":"house_test", "plotIndex":2,"houseAnchorLocalCFrame":[0]*12}]}))
        return db, manifest

    def test_database_and_placements_are_not_mutated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db, manifest = self.fixture(root)
            before_db, before_manifest = db.read_bytes(), manifest.read_bytes()
            data = preflight.inspect(root)
            self.assertEqual(data["registeredHouses"], 1)
            self.assertEqual(data["placementBindings"], 2)
            self.assertEqual(data["placementsWithoutHouseAnchor"], 1)
            self.assertEqual(data["distinctPlotsWithBindings"], 2)
            self.assertFalse(data["collisionMigrationEnabled"])
            self.assertEqual(data["houses"][0]["legacyColliders"][0]["name"], "col_mesh")
            self.assertEqual(data["houses"][0]["otherCollidableMeshes"][0]["name"], "door")
            self.assertEqual(db.read_bytes(), before_db)
            self.assertEqual(manifest.read_bytes(), before_manifest)

    def test_fail_closed_on_missing_database_or_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                preflight.inspect(Path(tmp))
            self.fixture(Path(tmp))
            (Path(tmp)/"assets/manifests/real-estate-placements.json").unlink()
            with self.assertRaises(FileNotFoundError):
                preflight.inspect(Path(tmp))

    def test_legacy_rig_classification_is_one_shared_contract(self):
        source = (PLUGIN / "modules/StudioRealEstateRigRoles.luau").read_text("utf-8")
        collision = (PLUGIN / "modules/StudioRealEstatePlacedCollisionSync.luau").read_text("utf-8")
        visuals = (PLUGIN / "modules/StudioRealEstatePlacedVisualSync.luau").read_text("utf-8")
        self.assertIn('instance:IsA("Model") and instance:GetAttribute("Game1RealEstatePhysicsRig") == true', source)
        self.assertIn("Roles.IsLegacyCollisionRig(rig)", collision)
        self.assertIn("Roles.IsLegacyCollisionRig(old)", collision)
        self.assertIn("Roles.IsVisualRig(child)", visuals)
        self.assertIn("not Roles.IsLegacyCollisionRig(instance)", source)

    def test_registered_in_both_plugin_bundlers(self):
        manifest = json.loads((PLUGIN/"plugin.project.json").read_text("utf-8"))
        self.assertEqual(manifest["tree"]["modules"]["StudioRealEstateRigRoles"]["$path"],
                         "modules/StudioRealEstateRigRoles.luau")
        self.assertIn("'StudioRealEstateRigRoles'", (PLUGIN/"install.ps1").read_text("utf-8"))

    def test_place_clear_still_use_unchanged_managed_contract(self):
        preview = (PLUGIN/"modules/StudioHousePlacementPreview.luau").read_text("utf-8")
        self.assertIn('ChangeHistoryService:TryBeginRecording', preview)
        self.assertIn('return executePlans(plans, "place_all")', preview)
        self.assertIn('return executePlans(plans, "clear_all")', preview)
        self.assertIn('HouseFrame.Find(', preview)


if __name__ == "__main__":
    unittest.main()
