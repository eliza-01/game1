"""M189: Character and Monster/NPC animation facade boundaries and publication invariants."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "system/control-center"))
from character_store import CharacterStore
from character_core.model_workflow import CharacterModelWorkflowMixin
from character_core.registry_export import CharacterRegistryExportMixin
from character_core.archetype_contract import CHARACTER_PUBLICATION_PIPELINE
from monster_store import MonsterStore
from monster_animation_store import MonsterAnimationStore
from monster_animation_core.schema import MonsterAnimationSchemaMixin
from monster_animation_core.bindings import MonsterAnimationBindingsMixin
from monster_animation_core.publication import MonsterAnimationPublicationMixin
from sqlite_connection import ClosingConnection


class CharacterAnimationBoundariesM189(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="game1-m189-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        original = sqlite3.connect
        def connection(*args, **kwargs):
            kwargs.setdefault("factory", ClosingConnection)
            return original(*args, **kwargs)
        patcher = mock.patch("sqlite3.connect", side_effect=connection)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_facades_delegate_to_owned_modules(self):
        self.assertIn(CharacterModelWorkflowMixin, CharacterStore.__mro__)
        self.assertIn(CharacterRegistryExportMixin, CharacterStore.__mro__)
        self.assertIn(MonsterAnimationSchemaMixin, MonsterAnimationStore.__mro__)
        self.assertIn(MonsterAnimationBindingsMixin, MonsterAnimationStore.__mro__)
        self.assertIn(MonsterAnimationPublicationMixin, MonsterAnimationStore.__mro__)
        self.assertNotIn("register", CharacterStore.__dict__)
        self.assertNotIn("publish_clip", MonsterAnimationStore.__dict__)
        self.assertEqual(CharacterStore.register.__module__, "character_core.model_workflow")
        self.assertEqual(MonsterAnimationStore._init.__module__, "monster_animation_core.schema")

    def test_character_published_asset_and_generated_registry_are_stable(self):
        store = CharacterStore(self.root)
        with store.connect() as db:
            db.execute("""INSERT INTO characters(
                id,display_name,source_path,prepared_path,sha256,model_asset_id,
                status,revision,created_at,updated_at,race,gender,
                published_sha256,publication_pipeline,bone_count
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                    "human_male", "Human Male", "assets/source/characters/human/male/human_male/model/human.fbx",
                    "assets/source/characters/human/male/human_male/model/human.fbx",
                    "unchanged-hash", "123456789", "PUBLISHED", 4, 100, 200, "human", "male",
                    "unchanged-hash", CHARACTER_PUBLICATION_PIPELINE, 6,
                ))
        source = self.root / "assets/source/characters/human/male/human_male/model/human.fbx"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"fixture-not-uploaded")
        store.export()
        with mock.patch("character_core.model_workflow.create_model_asset") as upload:
            result = store.publish("human_male", {})
        upload.assert_not_called()
        self.assertEqual(result["model_asset_id"], "123456789")
        self.assertEqual(store.snapshot()["items"][0]["status"], "PUBLISHED")
        store.set_active("human_male")
        self.assertEqual(store.runtime_selection()["modelAssetId"], "123456789")
        payload = json.loads((self.root / "assets/manifests/character-archetypes.json").read_text())
        self.assertEqual(payload["activeArchetypeId"], "human_male")
        self.assertEqual(payload["archetypes"][0]["model"]["assetId"], "123456789")
        registry = (self.root / "src/shared/character/CharacterRegistry.luau").read_text()
        self.assertIn('activeArchetypeId = "human_male"', registry)
        self.assertIn('assetId = "123456789"', registry)

    def test_npc_schema_mutations_and_publication_identity(self):
        (self.root / ".control-center").mkdir()
        actors = MonsterStore(self.root, kind="npc")
        with actors.connect() as db:
            db.execute("""INSERT INTO monsters(
                slug,name_en,model_source_path,model_asset_id,
                model_sha256,model_published_sha256,created_at,updated_at,skeleton_signature
            ) VALUES('blacksmith','Blacksmith','dummy','345','hash','hash',1,1,'signature')""")
        store = MonsterAnimationStore(self.root, kind="npc")
        with store.connect() as db:
            columns = {row[1] for row in db.execute("PRAGMA table_info(monster_animation_clips)")}
            self.assertIn("content_updated_at", columns)
            self.assertIn("source_sha256", columns)
            db.execute("""INSERT INTO monster_animation_clips
                (id,monster_slug,name,source_path,prepared_path,sha256,source_sha256,asset_id,
                 published_sha256,revision,created_at,updated_at,content_updated_at)
                VALUES('clip','blacksmith','idle_special','dummy','dummy','hash','hash','98765','hash',1,1,1,1)""")
            db.execute("""INSERT INTO monster_animation_bindings
                (id,monster_slug,slot,variant,clip_id,weight,looped,priority,created_at,updated_at,weapon_set)
                VALUES('binding','blacksmith','idle_special',1,'clip',100,0,'Idle',1,1,'base')""")
        (self.root / "dummy").write_bytes(b"registered-animation")
        with mock.patch("monster_animation_core.publication.create_animation_asset") as upload:
            published = store.publish_clip("clip", {})
        upload.assert_not_called()
        self.assertEqual(published["asset_id"], "98765")
        store.set_animation_options("binding", ["1hs", "unarmed"], 70, False)
        item = store.snapshot("blacksmith")["items"][0]
        self.assertEqual(item["asset_id"], "98765")
        self.assertEqual(item["weight"], 70)
        self.assertEqual(item["compatibleWith"], ["unarmed", "1hs"])
        with store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM monster_animation_publications").fetchone()[0], 0)
        registry = (self.root / "src/shared/npc/NpcAnimationRegistry.luau").read_text()
        self.assertIn('rbxassetid://98765', registry)
        self.assertIn('weight = 70', registry)


if __name__ == "__main__":
    unittest.main()
