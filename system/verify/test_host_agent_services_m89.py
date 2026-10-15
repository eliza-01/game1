"""M89 service contracts: Studio loading, native dialogs, and filesystem export."""
import base64
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "system/control-center"))
from services.studio_asset_sync import StudioAssetSyncService
from services.animation_export import write_animation_export
from services import native_pickers


class FakeStore:
    def __init__(self, data=None):
        self.data = data or {}
        self.queries = []

    def get(self, slug):
        self.queries.append(slug)
        return self.data.get(slug)


class StudioAssetSyncTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.result = {
            "rigStats": {"baseParts": 1, "bones": 2, "motor6Ds": 0,
                         "boneNames": ["Root", "Arm"]},
            "monsterStats": {"textures": {"applied": 1}},
        }
        self.characters = FakeStore({"hero": {
            "id": "hero", "race": "human", "gender": "female",
            "model_asset_id": "123", "skeleton_json": '{"bones":[{"name":"Root"},{"name":"Arm"}]}',
        }})
        self.weapons = FakeStore({"blade": {
            "slug": "blade", "weapon_type": "1hs", "rarity": "rare",
            "model_asset_id": "456", "textures": [{"slot": "main", "asset_id": "987"}],
        }})
        actor = {"slug": "smith", "model_asset_id": "789",
                 "skeleton_json": '{"bones":[{"name":"Root"},{"name":"Arm"}]}',
                 "textures": [{"slot": "base", "asset_id": "654"}]}
        self.monsters = FakeStore({"smith": actor})
        self.npcs = FakeStore({"smith": dict(actor)})

        def load(asset, destination, **kwargs):
            self.calls.append((asset, destination, kwargs))
            return self.result
        self.sync = StudioAssetSyncService(self.characters, self.weapons,
                                           self.monsters, self.npcs, load)

    def test_character_sync_validates_authored_skeleton_and_folder(self):
        out = self.sync.sync_character_to_studio("hero")
        self.assertEqual(out["character"]["id"], "hero")
        asset, destination, options = self.calls[-1]
        self.assertEqual(asset, "123")
        self.assertEqual(destination, ["characters", "human", "female", "hero", "model"])
        self.assertEqual(options["wrapper_name"], "hero")
        self.result["rigStats"]["boneNames"] = ["Root", "Other"]
        with self.assertRaisesRegex(ValueError, "stripped 1 of 2 registered bones"):
            self.sync.sync_character_to_studio("hero")

    def test_weapon_sync_preserves_pivot_metadata_and_texture_ids(self):
        out = self.sync.sync_weapon_to_studio("blade")
        self.assertEqual(out["weapon"]["slug"], "blade")
        asset, destination, options = self.calls[-1]
        self.assertEqual((asset, destination), ("456", ["weapons", "1hs", "blade", "model"]))
        self.assertEqual(options["placement_mode"], "weapon-pivot")
        self.assertEqual(options["metadata"]["textures"], [{"slot": "main", "assetId": "987"}])

    def test_npc_monster_sync_separate_repositories_and_expected_bones(self):
        self.sync.sync_monster_to_studio("smith", kind="npc")
        _, destination, options = self.calls[-1]
        self.assertEqual(destination, ["npcs", "smith", "model"])
        self.assertEqual(options["placement_mode"], "monster-rig")
        self.assertEqual(options["metadata"]["entityKind"], "npc")
        self.assertEqual(options["metadata"]["expectedBones"], ["Root", "Arm"])
        self.assertEqual(self.npcs.queries, ["smith"])
        self.assertEqual(self.monsters.queries, [])
        self.sync.sync_monster_to_studio("smith")
        self.assertEqual(self.calls[-1][1], ["monsters", "smith", "model"])
        self.assertEqual(self.monsters.queries, ["smith"])

    def test_monster_texture_and_rig_validation_still_block_bad_imports(self):
        self.result["monsterStats"]["textures"]["applied"] = 0
        with self.assertRaisesRegex(ValueError, "did not apply any published monster textures"):
            self.sync.sync_monster_to_studio("smith")
        self.result["monsterStats"]["textures"]["applied"] = 1
        self.result["rigStats"]["baseParts"] = 0
        with self.assertRaisesRegex(ValueError, "without an articulated rig"):
            self.sync.sync_monster_to_studio("smith")

    def test_rig_bone_count_fallback_and_no_expected_bones(self):
        self.result["rigStats"]["boneNames"] = []
        self.result["rigStats"]["bones"] = 1
        with self.assertRaisesRegex(ValueError, "returned only 1 of 2 registered bones"):
            self.sync.sync_monster_to_studio("smith", kind="npc")
        self.result["rigStats"]["bones"] = 2
        self.sync.sync_monster_to_studio("smith", kind="npc")
        self.characters.data["hero"]["skeleton_json"] = "not json"
        self.sync.sync_character_to_studio("hero")

    def test_missing_and_unpublished_models_never_contact_studio(self):
        with self.assertRaisesRegex(ValueError, "unknown npc"):
            self.sync.sync_monster_to_studio("missing", kind="npc")
        with self.assertRaisesRegex(ValueError, "unknown weapon"):
            self.sync.sync_weapon_to_studio("missing")
        self.assertEqual(self.calls, [])
        self.characters.data["hero"]["model_asset_id"] = ""
        with self.assertRaisesRegex(ValueError, "publish the character model"):
            self.sync.sync_character_to_studio("hero")
        self.assertEqual(self.calls, [])


class NativePickerTests(unittest.TestCase):
    def test_same_pickers_and_filter_specs_remain_public(self):
        with patch.object(native_pickers, "_powershell_picker", return_value="C:/asset.fbx") as picker:
            self.assertEqual(native_pickers.choose_character_fbx(), "C:/asset.fbx")
            self.assertIn("*.fbx", picker.call_args.args[0])
            self.assertEqual(native_pickers.choose_weapon_fbx(), "C:/asset.fbx")
            self.assertEqual(native_pickers.choose_location_asset_fbx(), "C:/asset.fbx")
        with patch.object(native_pickers, "_powershell_picker", return_value="a" + chr(31) + "b"):
            self.assertEqual(native_pickers.choose_monster_textures(), ["a", "b"])
            self.assertEqual(native_pickers.choose_weapon_textures(), ["a", "b"])
        with patch.object(native_pickers, "_powershell_picker", return_value=""):
            self.assertEqual(native_pickers.choose_monster_textures(), [])
            self.assertEqual(native_pickers.choose_character_fbx(), "")

    def test_animation_folder_uses_existing_environment_key(self):
        with patch.object(native_pickers, "_powershell_picker", return_value="C:/npc") as picker:
            self.assertEqual(native_pickers.choose_animation_folder(' "C:/clips" '), "C:/npc")
            self.assertEqual(picker.call_args.args[1], {
                "GAME1_ANIMATION_PICKER_INITIAL_PATH": "C:/clips"})


class AnimationExportTests(unittest.TestCase):
    def test_binary_export_overwrite_unicode_and_safe_filename(self):
        with tempfile.TemporaryDirectory() as temp:
            payload = {"outputDir": temp, "name": "тест:idle", "rbxmBase64": base64.b64encode(b"RBXM").decode()}
            first = write_animation_export(payload)
            self.assertEqual(Path(first["path"]).name, "тест_idle.rbxm")
            self.assertEqual(Path(first["path"]).read_bytes(), b"RBXM")
            self.assertEqual((first["overwrote"], first["bytes"]), (False, 4))
            payload["rbxmBase64"] = base64.b64encode(b"NEW").decode()
            second = write_animation_export(payload)
            self.assertTrue(second["overwrote"])
            self.assertEqual(Path(second["path"]).read_bytes(), b"NEW")
            self.assertFalse(Path(second["path"] + ".tmp").exists())

    def test_invalid_export_rejected_without_creating_files(self):
        with tempfile.TemporaryDirectory() as temp:
            bad_payloads = [
                ({"name": "idle", "rbxmBase64": "QQ=="}, "outputDir"),
                ({"outputDir": temp, "rbxmBase64": "QQ=="}, "name"),
                ({"outputDir": temp, "name": "idle", "rbxmBase64": "bad!?"}, "invalid animation"),
                ({"outputDir": temp, "name": "idle", "rbxmBase64": ""}, "rbxmBase64"),
                ({"outputDir": "relative/folder", "name": "idle", "rbxmBase64": "QQ=="}, "absolute path"),
            ]
            for data, message in bad_payloads:
                with self.subTest(data=data):
                    with self.assertRaisesRegex(ValueError, message):
                        write_animation_export(data)
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_service_modules_do_not_import_http_or_host_agent(self):
        services = ROOT / "system/control-center/services"
        for name in ("studio_asset_sync.py", "native_pickers.py", "animation_export.py"):
            source = (services / name).read_text(encoding="utf-8")
            with self.subTest(name=name):
                self.assertNotIn("import host_agent", source)
                self.assertNotIn("from http.server", source)
                self.assertNotIn("from api.", source)


if __name__ == "__main__":
    unittest.main()
