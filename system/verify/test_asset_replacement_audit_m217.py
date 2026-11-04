"""M217: complete cross-domain asset replacement audit contracts."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock
from contextlib import closing
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))

from api.write_dispatch import dispatch_delete, dispatch_post
from real_estate.jobs import RealEstatePublicationJobs
from services.sqlite_asset_audit_importer import SqliteAssetAuditImporter


class MemoryRepository:
    def __init__(self):
        self.events = []
    def ensure_schema(self):
        return None
    def append_publication(self, event):
        if not any(row['operationId'] == event['operationId'] for row in self.events):
            self.events.append(dict(event))
    def page_all(self, **_kwargs):
        return {'events': list(reversed(self.events)), 'nextCursor': None}


class AssetReplacementAuditM217(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / '.control-center').mkdir()
        self.repository = MemoryRepository()
        self.audit = SqliteAssetAuditImporter(self.root, self.repository)

    def source(self, path):
        return (ROOT / path).read_text(encoding='utf-8')

    def create_history(self):
        main = self.root / '.control-center/game1.db'
        with closing(sqlite3.connect(main)) as db:
            with db:
                db.executescript('''
                    CREATE TABLE character_publications(
                        id INTEGER PRIMARY KEY, character_id TEXT, character_revision INTEGER,
                        asset_id TEXT, operation_path TEXT, sha256 TEXT,
                        moderation_state TEXT, published_at REAL);
                    CREATE TABLE weapon_publications(
                        id INTEGER PRIMARY KEY, weapon_slug TEXT, kind TEXT, slot TEXT,
                        weapon_revision INTEGER, asset_id TEXT, operation_path TEXT,
                        sha256 TEXT, moderation_state TEXT, published_at REAL);
                    CREATE TABLE texture_atlas_publications(
                        id INTEGER PRIMARY KEY, variant_id INTEGER, image_asset_id TEXT,
                        sha256 TEXT, operation_path TEXT, moderation_state TEXT,
                        published_at REAL);
                ''')
                db.executemany(
                    'INSERT INTO character_publications VALUES(?,?,?,?,?,?,?,?)', [
                        (1, 'human_male', 1, '100', 'operations/a', 'a' * 64, '', 1000),
                        (2, 'human_male', 2, '200', 'operations/b', 'b' * 64, '', 2000),
                        # Same Roblox ID with new bytes is still an auditable revision.
                        (3, 'human_male', 3, '200', 'operations/c', 'c' * 64, '', 3000),
                    ])
                db.execute('INSERT INTO weapon_publications VALUES(?,?,?,?,?,?,?,?,?,?)',
                           (1, 'sword', 'model', '', 1, '300', 'operations/d',
                            'd' * 64, '', 4000))
                db.execute('INSERT INTO texture_atlas_publications VALUES(?,?,?,?,?,?,?)',
                           (1, 9, '400', 'e' * 64, 'operations/e', '', 5000))

    def test_imports_every_domain_idempotently_and_keeps_previous_id(self):
        self.create_history()
        first = self.audit.sync_all()
        second = self.audit.sync_all()
        self.assertEqual(first['scanned'], 5)
        self.assertEqual(second['scanned'], 5)
        self.assertEqual(len(self.repository.events), 5)
        character = [row for row in self.repository.events
                     if row['assetDomain'] == 'character']
        self.assertEqual([row['previousAssetId'] for row in character], ['', '100', '200'])
        self.assertEqual(character[-1]['assetId'], '200')
        self.assertEqual(character[-1]['sourceSha256'], 'c' * 64)
        self.assertEqual({row['assetDomain'] for row in self.repository.events},
                         {'character', 'weapon', 'texture_atlas'})

    def test_deletion_is_refused_when_audit_is_unavailable(self):
        audit = mock.Mock()
        audit.sync_all.side_effect = RuntimeError('mysql offline')
        handler = mock.Mock(return_value=(200, {'ok': True}))
        with mock.patch('api.write_dispatch.delete_entities.route', handler):
            status, payload = dispatch_delete('/api/weapons/sword', lambda: {}, {
                'asset_replacement_audit': audit,
            })
        self.assertEqual(status, 503)
        self.assertIn('deletion refused', payload['error'])
        handler.assert_not_called()

    def test_publication_is_audited_before_and_after(self):
        audit = mock.Mock()
        deps = {'asset_replacement_audit': audit}
        with mock.patch('api.write_dispatch.write_actors.route', return_value=(200, {'ok': True})):
            status, _ = dispatch_post('/api/weapons/sword/publish', lambda: {}, deps)
        self.assertEqual(status, 200)
        self.assertEqual(audit.sync_all.call_count, 2)

    def test_async_real_estate_publication_imports_after_success(self):
        store = mock.Mock()
        callback = mock.Mock()
        jobs = RealEstatePublicationJobs(store, on_succeeded=callback)
        job = {'status': 'queued', 'step': '', 'scope': 'all', 'error': '',
               'finishedAt': None}
        jobs._run('house_01', job, {'apiKey': 'not-persisted'})
        store.publish.assert_called_once()
        callback.assert_called_once_with()
        self.assertEqual(job['status'], 'succeeded')

    def test_mysql_and_ui_expose_generic_history(self):
        migration = self.source(
            'system/control-center/migrations/asset_audit_mysql/001_location_asset_sync_audit.sql')
        compose = self.source('system/control-center/compose.yaml')
        index = self.source('system/control-center/static/index.html')
        ui = self.source('system/control-center/static/asset-audit.js')
        self.assertIn('event_kind', migration)
        self.assertIn('asset_domain', migration)
        self.assertIn('source_system', migration)
        self.assertIn('mysql:8.4', compose)
        self.assertIn('game1-asset-audit-data', compose)
        self.assertIn('nav-asset-audit', index)
        self.assertIn('/api/asset-replacements?', ui)


if __name__ == '__main__':
    import unittest
    unittest.main()
