"""Offline contract tests for NPC authoring: no Studio, Roblox, network or project DB required."""
from __future__ import annotations

from pathlib import Path
import json
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "control-center"))
from monster_store import MonsterStore
from monster_animation_store import MonsterAnimationStore, classify
from monster_spawn_store import MonsterSpawnStore


class NpcPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="game1-npc-contract-")
        self.root = Path(self.temp.name)
        self.npcs = MonsterStore(self.root, kind="npc")
        self.monsters = MonsterStore(self.root, kind="monster")
        self.npc_animations = MonsterAnimationStore(self.root, kind="npc")
        self.bridge_calls = []

        def bridge(action, **kwargs):
            self.bridge_calls.append((action, kwargs))
            if action == "place":
                return {"mapKey": kwargs["map_key"], "placeId": 17, "position": {"x": 4, "y": 10, "z": 6}, "yawDegrees": 45}
            if action == "sync":
                return {"syncedSpawnIds": [row["spawnId"] for row in kwargs["records"]], "synchronized": True}
            return {"synchronized": True}

        self.spawns = MonsterSpawnStore(self.root, self.npcs, self.npc_animations, bridge, kind="npc")

    def tearDown(self):
        self.temp.cleanup()

    def test_sqlite_handles_are_closed_after_transactions(self):
        # A committed transaction is not enough: Windows locks an open DB file.
        for store in (self.monsters, self.npcs, self.npc_animations):
            with self.subTest(store=store.kind, cls=type(store).__name__):
                with store.connect() as db:
                    self.assertEqual(db.execute("SELECT 1").fetchone()[0], 1)
                with self.assertRaises(sqlite3.ProgrammingError):
                    db.execute("SELECT 1")

                with self.assertRaises(RuntimeError):
                    with store.connect() as failed:
                        failed.execute("SELECT 1")
                        raise RuntimeError("abort transaction")
                with self.assertRaises(sqlite3.ProgrammingError):
                    failed.execute("SELECT 1")

    def seed_npc(self):
        with self.npcs.connect() as db:
            db.execute(
                """INSERT INTO monsters(slug,name_en,model_source_path,model_sha256,model_asset_id,
                    model_published_sha256,created_at,updated_at,skeleton_signature)
                    VALUES(?,?,?,?,?,?,?,?,?)""",
                ("blacksmith", "Blacksmith", "assets/source/npcs/blacksmith/model/blacksmith.fbx",
                 "sha-model", "12345", "sha-model", 1.0, 1.0, "rig-1"),
            )
        self.npcs.export()
        self.npc_animations._sync_profiles()

    def seed_clips(self):
        animation_folder = self.root / "animation-inbox"
        animation_folder.mkdir(parents=True, exist_ok=True)
        for slot in ("idle", "death", "attack_01"):
            (animation_folder / f"blacksmith_1hs_{slot}.rbxm").write_bytes(slot.encode())
        scan = self.npc_animations.scan_folder("blacksmith", str(animation_folder))
        self.assertEqual(scan["recognized"], 3)
        self.assertEqual(scan["created"], 3)
        with self.npcs.connect() as db:
            db.execute("UPDATE monster_animation_clips SET asset_id='54321', published_sha256=sha256")
        self.npc_animations.export()

    def test_storage_and_registry_namespaces_are_isolated(self):
        self.seed_npc()
        self.assertEqual(len(self.npcs.list()), 1)
        self.assertEqual(self.monsters.list(), [])
        self.assertEqual(self.npcs.get("blacksmith")["status"], "PUBLISHED")
        registry = (self.root / "src/shared/npc/NpcRegistry.luau").read_text()
        self.assertIn('npcs = table.freeze({', registry)
        self.assertIn('ServerStorage.npcs.blacksmith.model.blacksmith', registry)
        self.assertEqual(self.npcs.db.name, "game1_npcs.db")
        self.assertEqual(self.monsters.db.name, "game1.db")

    def test_1hs_filename_binding_and_published_readiness(self):
        self.seed_npc()
        self.seed_clips()
        self.assertEqual(classify(Path("blacksmith_1hs_attack_02.rbxm"), "blacksmith", npc=True)["slot"], "attack")
        self.assertEqual(classify(Path("blacksmith_2hs_idle.rbxm"), "blacksmith", npc=True)["weaponSet"], "2hs")
        self.assertTrue(self.spawns.readiness("blacksmith")["ready"])
        registry = (self.root / "src/shared/npc/NpcAnimationRegistry.luau").read_text()
        self.assertIn('weaponSet = "1hs"', registry)
        self.assertIn('rbxassetid://54321', registry)
        self.assertIn("base", self.npc_animations.snapshot("blacksmith")["weaponSets"])
        self.assertIn("1hs", self.npc_animations.snapshot("blacksmith")["weaponSets"])

    def test_npc_spawns_without_any_animations(self):
        self.seed_npc()
        readiness = self.spawns.readiness("blacksmith")
        self.assertTrue(readiness["ready"])
        self.assertFalse(readiness["animationReady"])
        self.assertEqual(readiness["missingAnimationSlots"], ["idle", "death"])
        self.assertEqual(readiness["reasons"], [])
        choice = self.spawns.snapshot()["monsters"][0]
        self.assertTrue(choice["ready"])
        self.assertFalse(choice["animationReady"])
        draft = self.spawns.place({"monsterSlug": "blacksmith"})["draft"]
        self.spawns.register({**draft, "respawnSeconds": 2, "maxAlive": 1})
        self.assertTrue(self.spawns.validate()["ok"])

    def test_model_still_required_and_monster_rules_unchanged(self):
        self.seed_npc()
        with self.npcs.connect() as db:
            db.execute("UPDATE monsters SET model_asset_id=NULL WHERE slug='blacksmith'")
        self.npcs.export()
        self.assertFalse(self.spawns.readiness("blacksmith")["ready"])
        with self.assertRaisesRegex(ValueError, "blocked"):
            self.spawns.place({"monsterSlug": "blacksmith"})

        with self.monsters.connect() as db:
            db.execute(
                """INSERT INTO monsters(slug,name_en,model_source_path,model_sha256,model_asset_id,
                    model_published_sha256,created_at,updated_at,skeleton_signature)
                    VALUES(?,?,?,?,?,?,?,?,?)""",
                ("test_monster", "Test Monster", "assets/source/monsters/test_monster/model/test_monster.fbx",
                 "sha", "9876", "sha", 1.0, 1.0, "rig-1"),
            )
        self.monsters.export()
        monster_animations = MonsterAnimationStore(self.root, kind="monster")
        monster_spawns = MonsterSpawnStore(self.root, self.monsters, monster_animations, self.spawns.bridge)
        readiness = monster_spawns.readiness("test_monster")
        self.assertFalse(readiness["ready"])
        self.assertFalse(readiness["animationReady"])
        self.assertIn("Required published animations", " ".join(readiness["reasons"]))

    def test_npc_attack_radius_is_saved_for_existing_npc(self):
        self.seed_npc()
        updated = self.npcs.register({
            "slug": "blacksmith", "nameEn": "Blacksmith",
            "behavior": {"attackRadiusStuds": 8.5},
        })
        self.assertEqual(updated["behavior"]["attackRadiusStuds"], 8.5)
        self.assertEqual(self.npcs.get("blacksmith")["behavior"]["attackRadiusStuds"], 8.5)

    def test_npc_placement_preview_and_drag_rotation_contract(self):
        # The Studio gesture is isolated from monster authoring; runtime uses
        # the same yawDegrees from the final drag result, not camera yaw.
        repo = Path(__file__).resolve().parents[2]
        plugin_root = repo / "system/studio-plugin"
        project = json.loads((plugin_root / "plugin.project.json").read_text(encoding="utf-8"))
        modules = project["tree"]["modules"]
        self.assertIn("NpcSpawnPlacement", modules)
        self.assertIn("NpcSpawnPreview", modules)
        place_code = (plugin_root / "modules/NpcSpawnPlacement.luau").read_text(encoding="utf-8")
        preview_code = (plugin_root / "modules/NpcSpawnPreview.luau").read_text(encoding="utf-8")
        bridge_code = (plugin_root / "Game1Bridge.server.luau").read_text(encoding="utf-8")
        self.assertIn("mouse.Button1Down:Connect", place_code)
        self.assertIn("mouse.Button1Up:Connect", place_code)
        self.assertIn("mouse.X - initialX", place_code)
        self.assertIn("Escape", place_code)
        self.assertIn("CanQuery = false", preview_code)
        self.assertIn("NpcSpawnPreview.Attach", bridge_code)
        self.assertIn('if tostring(data.entityKind or "monster") == "npc"', bridge_code)

        self.seed_npc()
        result = self.spawns.place({"monsterSlug": "blacksmith", "yawDegrees": 12})
        draft = result["draft"]
        self.assertEqual(draft["yawDegrees"], 45)  # Studio gesture is authoritative.
        registered = self.spawns.register(draft)["record"]
        self.assertEqual(registered["yawDegrees"], 45)
        self.assertEqual(registered["position"], {"x": 4, "y": 10, "z": 6})

    def test_npc_idle_special_weights_export_and_per_npc_isolation(self):
        self.seed_npc()
        with self.npcs.connect() as db:
            db.execute(
                """INSERT INTO monsters(slug,name_en,model_source_path,model_sha256,model_asset_id,
                    model_published_sha256,created_at,updated_at,skeleton_signature)
                    VALUES(?,?,?,?,?,?,?,?,?)""",
                ("innkeeper", "Innkeeper", "assets/source/npcs/innkeeper/model/innkeeper.fbx",
                 "sha-other", "12346", "sha-other", 1.0, 1.0, "rig-2"),
            )
        self.npcs.export()
        self.npc_animations._sync_profiles()
        folder = self.root / "animations"
        folder.mkdir()
        for slug in ("blacksmith", "innkeeper"):
            for slot in ("idle", "idle_special_01", "idle_special_02"):
                (folder / f"{slug}_1hs_{slot}.rbxm").write_bytes(f"{slug}/{slot}".encode())
        # Each scanned folder contains only clips for that profile.
        for slug in ("blacksmith", "innkeeper"):
            individual = folder / slug
            individual.mkdir()
            for file in folder.glob(f"{slug}_1hs_*.rbxm"):
                file.rename(individual / file.name)
            self.assertEqual(self.npc_animations.scan_folder(slug, str(individual))["recognized"], 3)
        with self.npc_animations.connect() as db:
            db.execute("UPDATE monster_animation_clips SET asset_id='54321',published_sha256=sha256")
        self.npc_animations.export()
        rows = self.npc_animations.list_for_monster("blacksmith")
        base = next(row for row in rows if row["slot"] == "idle")
        special1 = next(row for row in rows if row["slot"] == "idle_special" and row["variant"] == 1)
        special2 = next(row for row in rows if row["slot"] == "idle_special" and row["variant"] == 2)
        self.npc_animations.set_weight(base["binding_id"], 300)
        self.npc_animations.set_weight(special1["binding_id"], 25)
        self.npc_animations.set_weight(special2["binding_id"], 0)
        manifest = json.loads((self.root / "assets/manifests/npc-animations.json").read_text())
        weights = {(row["monster_slug"], row["slot"], row["variant"]): row["weight"] for row in manifest["bindings"]}
        self.assertEqual(weights[("blacksmith", "idle", 0)], 300)
        self.assertEqual(weights[("blacksmith", "idle_special", 1)], 25)
        self.assertEqual(weights[("blacksmith", "idle_special", 2)], 0)
        self.assertEqual(weights[("innkeeper", "idle", 0)], 100)
        generated = (self.root / "src/shared/npc/NpcAnimationRegistry.luau").read_text()
        self.assertIn('role = "special"', generated)
        self.assertIn('sourceSlot = "idle_special"', generated)
        self.assertIn('weight = 0', generated)
        self.assertIn('weaponSet = "1hs"', generated)
        self.assertIn('["blacksmith"]', generated)
        self.assertIn('["innkeeper"]', generated)

    def test_npc_idle_runtime_wiring_and_zero_weight_api(self):
        repo = Path(__file__).resolve().parents[2]
        npc_root = repo / "src/server/npc"
        service = (npc_root / "NpcAnimationService.luau").read_text()
        idle = (npc_root / "NpcIdlePresentation.luau").read_text()
        tracks = (npc_root / "NpcAnimationTracks.luau").read_text()
        chooser = (repo / "src/shared/animation/WeightedAnimationChoice.luau").read_text()
        spawner = (npc_root / "NpcSpawnerService.luau").read_text()
        host = (repo / "system/control-center/host_agent.py").read_text()
        ui = (repo / "system/control-center/static/npc-assets.js").read_text()
        self.assertIn('WeightedAnimationChoice.Select(self.choices, selectionRandom)', idle)
        self.assertIn('self.base.track.DidLoop:Connect', idle)
        self.assertIn('Tracks.Step(self.base, delta)', idle)
        self.assertIn('Tracks.Step(special, delta)', idle)
        self.assertIn('self.activeSpecial', idle)
        self.assertIn('IdleVariant', idle)
        self.assertIn('weight > 0', chooser)
        self.assertIn('row.animationId', tracks)
        self.assertIn('first("death")', service)
        self.assertIn('idle:Step(delta)', service)
        self.assertIn('idle:Stop()', service)
        self.assertIn('entry.presentation.Step(delta)', spawner)
        self.assertIn('entry.presentation.Destroy()', spawner)
        self.assertIn('payload.get("weight", 100)', host)
        self.assertIn('data-weight class="weight-input" type="number" min="0"', ui)
        for module in (service, idle, tracks, chooser):
            self.assertNotIn('blacksmith', module)
            self.assertNotIn('innkeeper', module)

    def test_npc_special_exits_before_animation_track_fades_to_rest(self):
        repo = Path(__file__).resolve().parents[2]
        idle = (repo / "src/server/npc/NpcIdlePresentation.luau").read_text(encoding="utf-8")
        tracks = (repo / "src/server/npc/NpcAnimationTracks.luau").read_text(encoding="utf-8")
        config = (repo / "src/shared/npc/NpcAnimationConfig.luau").read_text(encoding="utf-8")
        self.assertIn("SpecialExitBlendSeconds = 0.15", config)
        self.assertIn("clip.track.Stopped:Connect", idle)
        self.assertNotIn("clip.track.Ended:Connect", idle)
        self.assertIn("local remaining = Tracks.SecondsRemaining(special)", idle)
        self.assertIn("remaining <= Config.SpecialExitBlendSeconds", idle)
        self.assertLess(idle.index("self:_playBase(fade)"), idle.index("Tracks.Stop(finished, fade)"))
        self.assertIn("clip.playbackSpeed = speed", tracks)
        self.assertIn("length - position) / speed", tracks)
        self.assertIn("RunService.PreAnimation:Connect", (repo / "src/server/npc/NpcSpawnerService.luau").read_text(encoding="utf-8"))

    def test_npc_runtime_preserves_authored_skeleton_before_loading_animation(self):
        # Regression: the old NPC factory inserted an artificial RootBone above
        # authored "spine", making animations deform the leg and upper-body branches.
        # CharacterRigService already preserves the imported bone hierarchy.
        repo = Path(__file__).resolve().parents[2]
        npc_factory = (repo / "src/server/npc/NpcRigFactory.luau").read_text(encoding="utf-8")
        spawner = (repo / "src/server/npc/NpcSpawnerService.luau").read_text(encoding="utf-8")
        character = (repo / "src/server/character/CharacterRigService.luau").read_text(encoding="utf-8")
        self.assertNotIn("bridgeRootBones", npc_factory)
        self.assertNotIn('Instance.new("Bone")', npc_factory)
        self.assertNotIn("bone.Parent =", npc_factory)
        self.assertNotIn('RuntimeAnimationRootBridgeCount', npc_factory)
        self.assertIn("published rig owns the bone hierarchy", npc_factory)
        self.assertIn("createRoot(character", character)
        self.assertLess(
            spawner.index("NpcRigFactory.Create(entity,"),
            spawner.index("NpcAnimationService.Create(entity, visual, profile)"),
        )

    def test_spawn_contract_delete_and_population_limits(self):
        self.seed_npc()
        self.seed_clips()
        draft = self.spawns.place({"monsterSlug": "blacksmith", "mapKey": "main"})["draft"]
        self.assertTrue(draft["spawnId"].startswith("spawn-"))
        result = self.spawns.register({**draft, "respawnSeconds": 7, "spawnRadius": 4, "maxAlive": 2})
        self.assertEqual(result["record"]["maxAlive"], 2)
        self.assertEqual(self.spawns.snapshot()["recordCount"], 1)
        self.assertEqual(len(self.spawns.monster_usage("blacksmith")), 1)
        manifest = json.loads((self.root / "assets/manifests/npc-spawns.json").read_text())
        self.assertEqual(len(manifest["records"]), 1)
        registry = (self.root / "src/server/npc/NpcSpawnRegistry.luau").read_text()
        self.assertIn('"respawnSeconds":7.0', registry)
        self.assertIn('"maxAlive":2', registry)
        self.assertTrue(self.spawns.validate()["ok"])
        self.spawns.delete({"spawnId": draft["spawnId"]})
        self.assertEqual(self.spawns.snapshot()["recordCount"], 0)

    def test_invalid_input_fails_closed(self):
        self.seed_npc()
        self.seed_clips()
        draft = self.spawns.place({"monsterSlug": "blacksmith"})["draft"]
        for changes in ({"maxAlive": 0}, {"maxAlive": 1001}, {"spawnRadius": -1},
                        {"respawnSeconds": -1}, {"position": {"x": float("nan"), "y": 0, "z": 1}}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.spawns.register({**draft, **changes})
        self.assertEqual(self.spawns.snapshot()["recordCount"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
