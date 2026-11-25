"""M483: CharacterStore must release its SQLite handle on Windows."""
from __future__ import annotations

from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'control-center'))
from character_store import CharacterStore


class CharacterStoreConnectionCleanupM483(unittest.TestCase):
    def test_connection_is_closed_on_success(self):
        with tempfile.TemporaryDirectory() as temp:
            store = CharacterStore(Path(temp))
            connection = store.connect()
            with connection as db:
                self.assertEqual(db.execute('select 1').fetchone()[0], 1)
            with self.assertRaises(sqlite3.ProgrammingError):
                connection.execute('select 1')
            self.assertEqual(store.list(), [])
        self.assertFalse(Path(temp).exists())

    def test_connection_is_closed_after_rollback(self):
        with tempfile.TemporaryDirectory() as temp:
            store = CharacterStore(Path(temp))
            connection = store.connect()
            with self.assertRaisesRegex(RuntimeError, 'rollback test'):
                with connection as db:
                    db.execute("insert into project_settings(key,value) values('m483','temp')")
                    raise RuntimeError('rollback test')
            with self.assertRaises(sqlite3.ProgrammingError):
                connection.execute('select 1')
            with store.connect() as db:
                self.assertIsNone(db.execute("select value from project_settings where key='m483'").fetchone())
        self.assertFalse(Path(temp).exists())


if __name__ == '__main__':
    unittest.main()
