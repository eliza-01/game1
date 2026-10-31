"""M178: scan preview is read-only, explicit registration and permanent ID replacement."""
from __future__ import annotations

import sqlite3
import warnings
import gc
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "control-center"))
from character_store import CharacterStore
from animation_store import AnimationStore


class AnimationReviewM178(unittest.TestCase):
    def setUp(self):
        self.warnings_context = warnings.catch_warnings()
        self.warnings_context.__enter__()
        warnings.filterwarnings("ignore", message="unclosed database", category=ResourceWarning)
        self.tmp=tempfile.TemporaryDirectory(prefix="game1-m178-")
        self.root=Path(self.tmp.name)
        self.inbox=self.root/'inbox'
        self.inbox.mkdir()
        characters=CharacterStore(self.root)
        with characters.connect() as db:
            db.execute("ALTER TABLE characters ADD COLUMN visual_mode TEXT NOT NULL DEFAULT 'model'")
            db.execute("""INSERT INTO characters (id,display_name,race,gender,skeleton_signature,visual_mode,created_at,updated_at)
                VALUES ('human_male','Male','human','male','shared-rig','assembly',0,0)""")
        self.store=AnimationStore(self.root)

    def tearDown(self):
        self.tmp.cleanup()
        gc.collect()
        self.warnings_context.__exit__(None, None, None)

    def clip(self, name='human_male_idle.rbxm', data=b'original'):
        path=self.inbox/name
        path.write_bytes(data)
        return path

    def test_preview_does_not_write_registry_or_copy_file(self):
        self.clip()
        original=self.store.snapshot('human_male')
        review=self.store.preview_folder('human_male',str(self.inbox))
        self.assertEqual((review['recognized'],review['items'][0]['status']), (1,'NEW'))
        self.assertEqual(self.store.snapshot('human_male'),original)
        self.assertFalse((self.root/'assets/source/characters/human/male/human_male/animations/base/base_idle.rbxm').exists())

    def test_selected_register_and_nonselected_remains_missing(self):
        path=self.clip()
        self.clip('human_male_walk.rbxm',b'walking')
        review=self.store.preview_folder('human_male',str(self.inbox))
        selected=next(row for row in review['items'] if row['path']==str(path))
        result=self.store.register_selected('human_male',str(self.inbox),[selected])
        self.assertEqual(result['count'],1)
        self.assertEqual([r['slot'] for r in self.store.snapshot('human_male')['items']], ['idle'])

    def test_stale_preview_cannot_register(self):
        path=self.clip()
        selected=self.store.preview_folder('human_male',str(self.inbox))['items'][0]
        path.write_bytes(b'new bytes')
        with self.assertRaisesRegex(ValueError,'scan again'):
            self.store.register_selected('human_male',str(self.inbox),[selected])
        self.assertEqual(self.store.snapshot('human_male')['items'],[])

    def test_published_changed_file_cannot_be_registered_from_scan(self):
        self.clip()
        r=self.store.preview_folder('human_male',str(self.inbox))['items'][0]
        self.store.register_selected('human_male',str(self.inbox),[r])
        clip=self.store.snapshot('human_male')['items'][0]
        with self.store.connect() as db:
            db.execute("UPDATE animation_clips SET asset_id='987',published_sha256=sha256 WHERE id=?",(clip['clip_id'],))
        self.clip(data=b'updated')
        review=self.store.preview_folder('human_male',str(self.inbox))['items'][0]
        self.assertEqual(review['status'],'REPLACE_REQUIRED')
        self.assertFalse(review['selectable'])
        with self.assertRaisesRegex(ValueError,'scan again'):
            self.store.register_selected('human_male',str(self.inbox),[review])
        self.assertEqual(self.store.snapshot('human_male')['items'][0]['status'],'PUBLISHED')

    def test_manual_replace_preserves_id_and_marks_pending(self):
        self.clip()
        r=self.store.preview_folder('human_male',str(self.inbox))['items'][0]
        self.store.register_selected('human_male',str(self.inbox),[r])
        clip=self.store.snapshot('human_male')['items'][0]
        with self.store.connect() as db:
            db.execute("UPDATE animation_clips SET asset_id='987',published_sha256=sha256 WHERE id=?",(clip['clip_id'],))
        replacement=self.clip('replacement.rbxm',b'replacement')
        result=self.store.stage_manual_replacement(clip['clip_id'],str(replacement))
        self.assertEqual(result['assetId'],'987')
        self.assertEqual(result['status'],'CHANGED')
        self.assertEqual(self.store.snapshot('human_male')['items'][0]['asset_id'],'987')

    def test_bad_filename_is_reported_and_not_registered(self):
        self.clip('random_unknown_xyz.rbxm')
        r=self.store.preview_folder('human_male',str(self.inbox))
        self.assertEqual(len(r['items']),0)
        self.assertEqual(len(r['unassigned']),1)
        self.assertEqual(self.store.snapshot('human_male')['items'],[])

    def test_missing_catalog_supports_assembly_without_migration(self):
        r=self.store.snapshot('human_male')
        self.assertTrue(r['slotCatalog']['base'])
        self.assertEqual(r['characterId'],'human_male')
        self.assertFalse(r['items'])
