"""M78: Remove must not resurrect old published IDs after Scan Folder."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "control-center"))
from animation_retirement import retire_unbound_clip
from monster_store import MonsterStore
from monster_animation_store import MonsterAnimationStore


class RemoveRescanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="game1-m78-")
        self.root = Path(self.tmp.name)
        self.folder = self.root / "inbox"
        self.folder.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def actor_store(self, kind):
        actors = MonsterStore(self.root, kind=kind)
        with actors.connect() as db:
            db.execute("""INSERT INTO monsters(slug,name_en,model_source_path,model_asset_id,
                model_sha256,model_published_sha256,created_at,updated_at,skeleton_signature)
                VALUES('sample','Sample','placeholder','123','a','a',0,0,'s')""")
        return MonsterAnimationStore(self.root, kind=kind)

    def seed_clip(self, animations, kind):
        name = 'sample_1hs_idle_special_01.rbxm' if kind == 'npc' else 'sample_idle_special_01.rbxm'
        source = self.folder / name
        source.write_bytes(b'original published bytes')
        scan = animations.scan_folder('sample', str(self.folder))
        self.assertEqual(scan['created'], 1)
        row = animations.snapshot('sample')['items'][0]
        with animations.connect() as db:
            db.execute("""UPDATE monster_animation_clips SET asset_id='987654321',
                published_sha256=sha256 WHERE id=?""", (row['clip_id'],))
            db.execute("""INSERT INTO monster_animation_publications
                (clip_id,clip_revision,asset_id,operation_path,sha256,published_at)
                VALUES(?,1,'987654321','publish-operation',(SELECT sha256 FROM monster_animation_clips WHERE id=?),1)""",
                (row['clip_id'],row['clip_id']))
        animations.export()
        return row, source

    def test_remove_and_rescan_is_fresh_registration_for_npc_and_monster(self):
        for kind in ('npc','monster'):
            with self.subTest(kind=kind):
                # A fresh temp directory per subtest avoids cross-kind database conflicts.
                with tempfile.TemporaryDirectory(prefix=f'game1-m78-{kind}-') as directory:
                    original_root, original_folder = self.root, self.folder
                    try:
                        self.root = Path(directory)
                        self.folder = self.root / 'inbox'
                        self.folder.mkdir()
                        animations = self.actor_store(kind)
                        row, source = self.seed_clip(animations,kind)
                        animations.delete_binding(row['binding_id'])
                        self.assertEqual(animations.snapshot('sample')['items'], [])
                        with animations.connect() as db:
                            retired = db.execute('SELECT * FROM animation_registration_archive').fetchall()
                            self.assertEqual(len(retired),1)
                            self.assertEqual(retired[0]['asset_id'],'987654321')
                            self.assertEqual(json.loads(retired[0]['publications_json'])[0]['asset_id'],'987654321')
                            self.assertEqual(db.execute('SELECT COUNT(*) FROM monster_animation_publications').fetchone()[0],0)
                        self.assertTrue(source.exists())
                        rescanned = animations.scan_folder('sample',str(self.folder))
                        self.assertEqual((rescanned['created'],rescanned['changed']), (1,0))
                        fresh = animations.snapshot('sample')['items'][0]
                        self.assertEqual(fresh['status'],'LOCAL_ONLY')
                        self.assertIsNone(fresh['asset_id'])
                        self.assertEqual(fresh['revision'],1)
                        self.assertEqual(len(animations.snapshot('sample')['items']),1)
                    finally:
                        self.root, self.folder = original_root, original_folder

    def test_startup_migrates_preexisting_published_orphan_but_not_active_binding(self):
        animations = self.actor_store('npc')
        old, source = self.seed_clip(animations,'npc')
        # Simulate the historical (M77) Remove behavior: binding is gone but
        # the published clip and its old cloud ID remain in the active table.
        with animations.connect() as db:
            db.execute('DELETE FROM monster_animation_bindings WHERE id=?', (old['binding_id'],))
        animations.export()
        self.assertEqual(animations.snapshot('sample')['items'], [])
        animations = MonsterAnimationStore(self.root,kind='npc')
        with animations.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM monster_animation_clips').fetchone()[0],0)
            archive = db.execute('SELECT asset_id FROM animation_registration_archive').fetchone()
            self.assertEqual(archive['asset_id'],'987654321')
        scan = animations.scan_folder('sample',str(self.folder))
        self.assertEqual(scan['created'],1)
        self.assertEqual(animations.snapshot('sample')['items'][0]['status'],'LOCAL_ONLY')
        # A new application boot must not archive an active registration.
        animations = MonsterAnimationStore(self.root,kind='npc')
        self.assertEqual(len(animations.snapshot('sample')['items']),1)

    def test_retirement_refuses_to_remove_shared_clip_still_in_use(self):
        animations = self.actor_store('npc')
        row, _ = self.seed_clip(animations,'npc')
        with animations.connect() as db:
            self.assertFalse(retire_unbound_clip(db,'npc',row['clip_id']))
            self.assertEqual(db.execute('SELECT COUNT(*) FROM monster_animation_clips').fetchone()[0],1)

    def test_character_retirement_and_old_publication_history(self):
        import sqlite3
        from animation_retirement import retire_legacy_orphans
        db = sqlite3.connect(':memory:')
        db.row_factory=sqlite3.Row
        try:
            db.executescript('''
                CREATE TABLE animation_clips(id TEXT PRIMARY KEY, asset_id TEXT);
                CREATE TABLE animation_bindings(clip_id TEXT);
                CREATE TABLE animation_publications(id INTEGER PRIMARY KEY, clip_id TEXT, asset_id TEXT);
                INSERT INTO animation_clips VALUES ('clip','111');
                INSERT INTO animation_publications VALUES (1,'clip','111');
                INSERT INTO animation_publications VALUES (2,'removed-without-clip','222');
            ''')
            self.assertEqual(retire_legacy_orphans(db,'character'),2)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM animation_clips').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM animation_publications').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM animation_registration_archive').fetchone()[0],2)
        finally:
            db.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
