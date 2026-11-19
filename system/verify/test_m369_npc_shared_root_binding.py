"""M369: reused NPC clips preserve the source rig's root MeshPart binding."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "system/control-center"))
from monster_store import MonsterStore
from monster_animation_store import MonsterAnimationStore


class SharedNpcRootBindingTests(unittest.TestCase):
    def test_registry_identifies_actual_clip_owner_not_recipient(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            actors = MonsterStore(root, kind="npc")
            with actors.connect() as db:
                for slug in ("donor", "recipient"):
                    db.execute("""INSERT INTO monsters(slug,name_en,model_source_path,model_sha256,
                        model_asset_id,model_published_sha256,created_at,updated_at,
                        skeleton_signature,skeleton_structure_signature)
                        VALUES (?,?,?,?,?,?,?,?,?,?)""",
                        (slug, slug, f"assets/source/npcs/{slug}/model.fbx", "hash", "123", "hash",
                         0, 0, "skel", "structure"))
            store = MonsterAnimationStore(root, kind="npc")
            inbox = root / "inbox"
            inbox.mkdir()
            (inbox / "donor_base_death.rbxm").write_bytes(b"animation")
            store.scan_folder("donor", str(inbox))
            with store.connect() as db:
                db.execute("UPDATE monster_animation_clips SET asset_id='123456789', published_sha256=sha256")
            source_binding = store.snapshot("donor")["items"][0]["binding_id"]
            store.connect_existing("recipient", "donor", [source_binding])
            text = (root / "src/shared/npc/NpcAnimationRegistry.luau").read_text(encoding="utf-8")
            recipient = text.split('["recipient"] = table.freeze({', 1)[1]
            self.assertIn('sourceNpc = "donor"', recipient)
            self.assertIn('rbxassetid://123456789', recipient)
            self.assertNotIn('sourceNpc = "recipient"', recipient)
            self.assertEqual(text.count('sourceNpc = "donor"'), 2)
            store = MonsterAnimationStore(root, kind="npc")
            store.export()
            self.assertIn('sourceNpc = "donor"',
                          (root / "src/shared/npc/NpcAnimationRegistry.luau").read_text(encoding="utf-8"))

    def test_gear_context_and_rig_alignment_run_before_loading_tracks(self):
        spawn = (ROOT / 'src/server/npc/NpcSpawnerService.luau').read_text(encoding='utf-8')
        start = spawn.index('local weaponSet = NpcEquipmentService.Equip(entity, slug)')
        bind = spawn.index('NpcAnimationRigBinding.Align(visual, slug, profile, weaponSet)')
        load = spawn.index('NpcAnimationService.Create(entity, visual, profile)')
        self.assertLess(start, bind)
        self.assertLess(bind, load)
        self.assertIn('local NpcAnimationRigBinding = require(', spawn)

    def test_only_spawned_root_meshpart_renamed_after_structure_preflight(self):
        luau = (ROOT / 'src/server/npc/NpcAnimationRigBinding.luau').read_text(encoding='utf-8')
        self.assertIn('NpcRegistry', luau)
        self.assertIn('serverStoragePath', luau)
        self.assertIn('Compatibility.Allowed(row, weaponSet)', luau)
        self.assertIn('origin.skeleton ~= targetSkeleton', luau)
        self.assertIn('requiredName ~= origin.name', luau)
        self.assertIn('root:SetAttribute("Game1OriginalMeshName", root.Name)', luau)
        self.assertIn('root.Name = requiredName', luau)
        self.assertNotIn('Bone:Clone()', luau)
        self.assertNotIn('RootBone', luau)
        self.assertNotIn('Heartbeat', luau)
        self.assertNotIn('RenderStepped', luau)

    def test_existing_real_registry_guard02_uses_guard01_clips(self):
        registry = (ROOT / 'src/shared/npc/NpcAnimationRegistry.luau').read_text(encoding='utf-8')
        guard02 = registry.split('["guard_02"] = table.freeze({', 1)[1].split('["warsmith"] = table.freeze({', 1)[0]
        self.assertEqual(guard02.count('sourceNpc = "guard_01"'), 7)
        self.assertEqual(guard02.count('sourceNpc = "guard_02"'), 0)
        self.assertIn('assetId = "140129007932289"', guard02)


if __name__ == '__main__':
    unittest.main()
