"""M474: publication queue is read-only, global and excludes unsafe uploads."""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1] / 'control-center'
sys.path.insert(0, str(HERE))
from animation_core.publication_queue import AnimationPublicationQueueMixin
from api.read_catalog import route
from animation_core.publication import AnimationPublicationMixin
from threading import Event, Thread


class FakeStore(AnimationPublicationQueueMixin):
    def __init__(self, db):
        self.db = db

    def connect(self):
        connection = sqlite3.connect(self.db)
        connection.row_factory = sqlite3.Row
        return connection


class AnimationQueueM474(unittest.TestCase):
    def test_pending_all_genders_common_and_deduplicated(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / 'game1.db'
            with closing(sqlite3.connect(db)) as conn, conn:
                conn.executescript('''
                    create table animation_clips(id text, name text, character_id text,
                        asset_id text, source_path text, prepared_path text, sha256 text);
                    create table animation_bindings(clip_id text, scope text, weapon_set text,
                        slot text, variant integer);
                ''')
                clips = [
                    ('common', 'human_common_social_laugh_01', 'human_common', None, 'a.rbxm', 'a.rbxm', 'a'),
                    ('male', 'human_male_social_hi_01', 'human_male', '', 'b.rbxm', 'b.rbxm', 'b'),
                    ('female', 'human_female_social_bow_01', 'human_female', None, 'c.rbxm', 'c.rbxm', 'c'),
                    ('published', 'published', 'human_female', '1234', 'd.rbxm', 'd.rbxm', 'd'),
                    ('changed', 'changed', 'human_male', '1235', 'e.rbxm', 'e.rbxm', 'e'),
                    ('document', 'document', 'human_male', None, 'f.animation.json', 'f.animation.json', 'f'),
                    ('missing', 'missing', 'human_male', None, 'g.rbxm', '', 'g'),
                ]
                conn.executemany('insert into animation_clips values(?,?,?,?,?,?,?)', clips)
                for clip in clips:
                    conn.execute('insert into animation_bindings values(?,?,?,?,?)', (clip[0], 'social', '', 'hi', 1))
                conn.execute('insert into animation_bindings values(?,?,?,?,?)', ('common', 'social', '', 'hi', 1))
            store = FakeStore(db)
            rows = store.pending_publications()
            self.assertEqual([row['clipId'] for row in rows], ['common', 'female', 'male'])
            self.assertTrue(all(row['status']=='LOCAL_ONLY' for row in rows))
            self.assertEqual(rows[0]['characterId'], 'human_common')
            from urllib.parse import urlparse
            status, response = route(urlparse('/api/animations/publish-queue'), {'animations': store}, lambda: {'configured': True})
            self.assertEqual(status, 200)
            self.assertEqual(response['items'], rows)
            self.assertTrue(response['publication']['configured'])

    def test_same_clip_concurrent_publication_is_rejected(self):
        entered, release = Event(), Event()
        results = []

        class Stub(AnimationPublicationMixin):
            def _publish_clip_unlocked(self, clip_id, credentials):
                entered.set()
                self.assertion = release.wait(5)
                return {'asset_id': '12345'}

        store = Stub()
        thread = Thread(target=lambda: results.append(store.publish_clip('clip', {})))
        thread.start()
        self.assertTrue(entered.wait(3))
        try:
            with self.assertRaisesRegex(ValueError, 'already running'):
                store.publish_clip('clip', {})
        finally:
            release.set()
            thread.join(timeout=5)
        self.assertEqual(results, [{'asset_id': '12345'}])


if __name__ == '__main__':
    unittest.main()
