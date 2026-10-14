"""M84: duplicate-slot scan does not throw, overwrite registrations or revive removed IDs."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "control-center"))
from monster_store import MonsterStore
from monster_animation_store import MonsterAnimationStore
from animation_scan_conflicts import partition_scan_candidates


class AnimationScanConflictsM84(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="game1-m84-")
        self.root = Path(self.tmp.name)
        self.inbox = self.root / "inbox"
        self.inbox.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def store(self, kind: str):
        actors = MonsterStore(self.root, kind=kind)
        with actors.connect() as db:
            db.execute("""INSERT INTO monsters(slug,name_en,model_source_path,model_asset_id,
                model_sha256,model_published_sha256,created_at,updated_at,skeleton_signature)
                VALUES('example','Example','placeholder','123','a','a',0,0,'s')""")
        return MonsterAnimationStore(self.root, kind=kind)

    def seed(self, names: tuple[str, ...]):
        for name in names:
            (self.inbox / name).write_bytes(name.encode())

    def test_npc_two_aliases_are_unassigned_and_safe(self):
        animations = self.store("npc")
        names = ("example_1hs_combat_idle.rbxm", "example_1hs_idle_combat.rbxm",
                 "example_base_death.rbxm")
        self.seed(names)
        result = animations.scan_folder("example", str(self.inbox))
        self.assertEqual(result["created"], 1)
        self.assertEqual(result["recognized"], 1)
        self.assertEqual(len(result["unassigned"]), 2)
        self.assertTrue(all("1hs / combat_idle / 00" in item["reason"] for item in result["unassigned"]))
        self.assertEqual([r["slot"] for r in animations.snapshot("example")["items"]], ["death"])
        self.assertTrue(all("conflict" in item["reason"].lower() for item in result["unassigned"]))

    def test_removed_registration_stays_archived_after_conflicting_scan(self):
        animations = self.store("npc")
        path = self.inbox / "example_1hs_combat_idle.rbxm"
        path.write_bytes(b"published-original")
        animations.scan_folder("example", str(self.inbox))
        row = animations.snapshot("example")["items"][0]
        with animations.connect() as db:
            db.execute("UPDATE monster_animation_clips SET asset_id='777',published_sha256=sha256 WHERE id=?",(row["clip_id"],))
        animations.delete_binding(row["binding_id"])
        self.assertEqual(animations.snapshot("example")["items"], [])
        (self.inbox / "example_1hs_idle_combat.rbxm").write_bytes(b"alternate")
        result = animations.scan_folder("example", str(self.inbox))
        self.assertEqual(result["recognized"], 0)
        self.assertEqual(result["created"], 0)
        self.assertEqual(len(result["unassigned"]), 2)
        with animations.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM monster_animation_clips").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT asset_id FROM animation_registration_archive").fetchone()[0], '777')
        (self.inbox / "example_1hs_idle_combat.rbxm").unlink()
        result = animations.scan_folder("example", str(self.inbox))
        self.assertEqual((result["created"],result["changed"]),(1,0))
        row = animations.snapshot("example")["items"][0]
        self.assertEqual(row["status"], "LOCAL_ONLY")
        self.assertFalse(row["asset_id"])

    def test_monster_duplicate_aliases_are_not_registered(self):
        animations = self.store("monster")
        self.seed(("example_attack_01.rbxm", "example_atk_01.rbxm"))
        result = animations.scan_folder("example",str(self.inbox))
        self.assertEqual((result["recognized"],len(result["unassigned"])),(0,2))
        self.assertIn("attack / 01",result["unassigned"][0]["reason"])
        self.assertEqual(animations.snapshot("example")["items"],[])

    def test_helper_produces_no_number_format_exceptions(self):
        a=(Path("a.rbxm"), {"weaponSet":"1hs","slot":"idle_special","variant":3})
        b=(Path("b.rbxmx"), {"weaponSet":"1hs","slot":"idle_special","variant":3})
        good, bad = partition_scan_candidates([a,b],kind="npc")
        self.assertFalse(good)
        self.assertEqual(len(bad),2)
        self.assertIn("1hs / idle_special / 03",bad[0]["reason"])
        with self.assertRaises(ValueError):
            partition_scan_candidates([],kind="player")


if __name__ == "__main__":
    unittest.main(verbosity=2)
