"""M359: Windows-safe SQLite lifecycle for WeaponStore transactions."""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from weapon_store import WeaponStore


class WeaponSqliteLifecycleM359(unittest.TestCase):
    def test_commit_rollback_and_handles_are_closed(self):
        with tempfile.TemporaryDirectory(prefix='m359-weapon-db-') as tmp:
            root = Path(tmp)
            store = WeaponStore(root)
            with store.connect() as committed:
                committed.execute(
                    "INSERT INTO project_settings(key,value) VALUES(?,?)",
                    ('m359_committed', 'yes'),
                )
            # Connection must be closed immediately, not eventually by GC.
            with self.assertRaises(sqlite3.ProgrammingError):
                committed.execute('SELECT 1')

            with self.assertRaisesRegex(RuntimeError, 'intentional rollback'):
                with store.connect() as rolled_back:
                    rolled_back.execute(
                        "INSERT INTO project_settings(key,value) VALUES(?,?)",
                        ('m359_rolled_back', 'no'),
                    )
                    raise RuntimeError('intentional rollback')
            with self.assertRaises(sqlite3.ProgrammingError):
                rolled_back.execute('SELECT 1')

            with store.connect() as check:
                self.assertEqual(
                    check.execute("SELECT value FROM project_settings WHERE key='m359_committed'").fetchone()[0],
                    'yes',
                )
                self.assertIsNone(check.execute(
                    "SELECT value FROM project_settings WHERE key='m359_rolled_back'"
                ).fetchone())
            with self.assertRaises(sqlite3.ProgrammingError):
                check.execute('SELECT 1')
            # TemporaryDirectory cleanup exercises the file-unlock case on Windows.


if __name__ == '__main__':
    unittest.main()
