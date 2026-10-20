"""M116: authoring SQLite handles close on both success and exception."""
from __future__ import annotations

import sqlite3
import hashlib
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from location_asset_store import LocationAssetStore
from audit_authoring_databases import audit_database


class LocationAssetConnectionLifecycleTests(unittest.TestCase):
    def test_success_commits_and_closes_handle(self):
        with tempfile.TemporaryDirectory(prefix='m116-sqlite-close-') as tmp:
            store = LocationAssetStore(Path(tmp))
            with store.connect() as db:
                db.execute('CREATE TABLE lifecycle_test (value TEXT NOT NULL)')
                db.execute("INSERT INTO lifecycle_test(value) VALUES ('committed')")
            with self.assertRaises(sqlite3.ProgrammingError):
                db.execute('SELECT 1')
            with store.connect() as db:
                self.assertEqual(db.execute('SELECT value FROM lifecycle_test').fetchone()[0], 'committed')
            with self.assertRaises(sqlite3.ProgrammingError):
                db.execute('SELECT 1')

    def test_exception_rolls_back_and_closes_handle(self):
        with tempfile.TemporaryDirectory(prefix='m116-sqlite-rollback-') as tmp:
            store = LocationAssetStore(Path(tmp))
            with store.connect() as db:
                db.execute('CREATE TABLE lifecycle_test (value TEXT NOT NULL)')
            with self.assertRaisesRegex(RuntimeError, 'abort'):
                with store.connect() as db:
                    db.execute("INSERT INTO lifecycle_test(value) VALUES ('uncommitted')")
                    raise RuntimeError('abort')
            with self.assertRaises(sqlite3.ProgrammingError):
                db.execute('SELECT 1')
            with store.connect() as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM lifecycle_test').fetchone()[0], 0)


class ReadOnlyDatabaseAuditTests(unittest.TestCase):
    def test_backup_and_audit_never_edit_source(self):
        with tempfile.TemporaryDirectory(prefix='m116-audit-') as tmp:
            root = Path(tmp)
            source = root / 'game1.db'
            with closing(sqlite3.connect(source)) as db:
                db.execute('CREATE TABLE location_assets (slug TEXT PRIMARY KEY, texture_filename TEXT NOT NULL)')
                db.execute("INSERT INTO location_assets VALUES ('granite', 'Granite Atlas.png')")
                db.commit()
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            count, digest = audit_database(source, backup_dir=root / 'backups', require_m115=True)
            self.assertEqual(count, 1)
            self.assertEqual(len(digest), 64)
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)
            with closing(sqlite3.connect(root / 'backups' / 'game1.db')) as backup:
                self.assertEqual(backup.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
                self.assertEqual(backup.execute('SELECT slug FROM location_assets').fetchone()[0], 'granite')
            with self.assertRaises(FileExistsError):
                audit_database(source, backup_dir=root / 'backups', require_m115=True)

    def test_missing_m115_schema_is_reported_readonly(self):
        with tempfile.TemporaryDirectory(prefix='m116-audit-schema-') as tmp:
            source = Path(tmp) / 'game1.db'
            with closing(sqlite3.connect(source)) as db:
                db.execute('CREATE TABLE location_assets (slug TEXT PRIMARY KEY)')
            with self.assertRaisesRegex(RuntimeError, 'texture_filename'):
                audit_database(source, require_m115=True)
            with closing(sqlite3.connect(source)) as db:
                self.assertEqual([row[1] for row in db.execute('PRAGMA table_info(location_assets)')], ['slug'])


if __name__ == '__main__':
    unittest.main()
