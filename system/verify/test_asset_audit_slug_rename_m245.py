"""M245: existing MySQL audit identities survive Location slug renames."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services.asset_audit_historical_identity import slug_at_publication
from services.mysql_asset_replacement_audit import MySqlAssetReplacementAudit
from services.sqlite_asset_audit_importer import SqliteAssetAuditImporter


class StrictAuditRepository:
    """Mimics the operation/source identity guard of the real MySQL writer."""
    def __init__(self):
        self.events = {}

    def ensure_schema(self):
        pass

    def append_publications(self, events):
        for event in events:
            source = (event['sourceSystem'], event['sourceRecord'])
            old = self.events.get(source)
            if old and (old['assetDomain'], old['assetKey']) != (event['assetDomain'], event['assetKey']):
                raise ValueError('audit operation identity belongs to a different asset')
            if old and (old['assetId'], old['sourceSha256']) != (event['assetId'], event['sourceSha256']):
                raise ValueError('changed immutable publication contents')
            self.events.setdefault(source, dict(event))


class AuditSlugRenameM245(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        db_path = self.root / '.control-center' / 'game1.db'
        db_path.parent.mkdir(parents=True)
        self.path = db_path
        with sqlite3.connect(self.path) as db:
            db.executescript('''
                CREATE TABLE location_asset_publications (
                    id INTEGER PRIMARY KEY, asset_slug TEXT, kind TEXT, revision INTEGER,
                    asset_id TEXT, operation_path TEXT, sha256 TEXT, published_at REAL);
                CREATE TABLE texture_atlas_legacy_publications (
                    id INTEGER PRIMARY KEY, consumer_type TEXT, consumer_id TEXT,
                    source_sha256 TEXT, image_asset_id TEXT, imported_at REAL);
                CREATE TABLE location_asset_slug_aliases (
                    old_slug TEXT PRIMARY KEY, current_slug TEXT, renamed_at REAL);
            ''')
            db.execute('INSERT INTO location_asset_publications VALUES (1,?,?,?,?,?,?,?)',
                       ('old_tree', 'model', 1, '12001', 'asset/a', 'sha1', 10))
            db.execute('INSERT INTO texture_atlas_legacy_publications VALUES (1,?,?,?,?,?)',
                       ('location_asset', 'old_tree', 'atlas-sha', '22001', 20))
            db.execute('INSERT INTO texture_atlas_legacy_publications VALUES (2,?,?,?,?,?)',
                       ('real_estate', 'house_01:window', 'house-sha', '33001', 30))
        self.repository = StrictAuditRepository()
        self.importer = SqliteAssetAuditImporter(self.root, self.repository)

    def rename(self, old, new, when):
        with sqlite3.connect(self.path) as db:
            db.execute('UPDATE location_asset_publications SET asset_slug=? WHERE asset_slug=?',
                       (new, old))
            db.execute("UPDATE texture_atlas_legacy_publications SET consumer_id=? "
                       "WHERE consumer_type='location_asset' AND consumer_id=?", (new, old))
            db.execute('UPDATE location_asset_slug_aliases SET current_slug=? WHERE current_slug=?',
                       (new, old))
            db.execute('INSERT INTO location_asset_slug_aliases VALUES (?,?,?)', (old, new, when))

    def test_renames_do_not_mutate_existing_audit_identity(self):
        self.importer.sync_all()
        initial = {source: dict(event) for source, event in self.repository.events.items()}
        self.rename('old_tree', 'tree_01', 100)
        self.importer.sync_all()  # Previously rejected every audited write.
        for source, original in initial.items():
            self.assertEqual(self.repository.events[source], original)
        with sqlite3.connect(self.path) as db:
            db.execute('INSERT INTO location_asset_publications VALUES (2,?,?,?,?,?,?,?)',
                       ('tree_01', 'model', 2, '12002', 'asset/b', 'sha2', 150))
        self.importer.sync_all()
        new_publication = next(event for event in self.repository.events.values()
                               if event['assetId'] == '12002')
        self.assertEqual(new_publication['assetKey'], 'tree_01')
        self.assertEqual(new_publication['previousAssetId'], '12001')

        self.rename('tree_01', 'tree_final', 200)
        self.importer.sync_all()
        self.assertEqual(next(event for event in self.repository.events.values()
                              if event['assetId'] == '12001')['assetKey'], 'old_tree')
        self.assertEqual(next(event for event in self.repository.events.values()
                              if event['assetId'] == '12002')['assetKey'], 'tree_01')
        with sqlite3.connect(self.path) as db:
            db.execute('INSERT INTO location_asset_publications VALUES (3,?,?,?,?,?,?,?)',
                       ('tree_final', 'model', 3, '12003', 'asset/c', 'sha3', 250))
        self.importer.sync_all()
        self.assertEqual(next(event for event in self.repository.events.values()
                              if event['assetId'] == '12003')['assetKey'], 'tree_final')
        self.assertEqual(next(event for event in self.repository.events.values()
                              if event['assetId'] == '33001')['assetKey'], 'house_01:window')
        self.assertEqual(len(self.repository.events), 5)

    def test_atlas_publish_preflight_survives_renamed_location_history(self):
        from api.write_dispatch import dispatch_post
        self.importer.sync_all()
        self.rename('old_tree', 'tree_01', 100)
        with (mock.patch('api.write_dispatch.real_estate.write', return_value=None),
              mock.patch('api.write_dispatch.write_files.route', return_value=None),
              mock.patch('api.write_dispatch.write_actors.route', return_value=None),
              mock.patch('api.write_dispatch.write_world.route', return_value=(200, {'publishedAssetId': '88001'})) as publish,
              mock.patch('api.write_dispatch.write_animations.route', return_value=None)):
            status, payload = dispatch_post('/api/texture-atlases/publish-reviewed',
                                            lambda: {'sha256': 'example'},
                                            {'asset_replacement_audit': self.importer})
        self.assertEqual((status, payload['publishedAssetId']), (200, '88001'))
        publish.assert_called_once()

    def test_unrelated_publication_rebinding_is_still_rejected(self):
        self.importer.sync_all()
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE location_asset_publications SET asset_slug='some_other_tree' WHERE id=1")
        with self.assertRaisesRegex(ValueError, 'different asset'):
            self.importer.sync_all()

    def test_rename_history_is_time_ordered_not_alphabetical(self):
        aliases = [
            {'old_slug': 'first', 'current_slug': 'last', 'renamed_at': 100},
            {'old_slug': 'middle', 'current_slug': 'last', 'renamed_at': 200},
        ]
        self.assertEqual(slug_at_publication('last', 50, aliases), 'first')
        self.assertEqual(slug_at_publication('last', 150, aliases), 'middle')
        self.assertEqual(slug_at_publication('last', 250, aliases), 'last')

    def test_mysql_writer_still_rejects_different_assets(self):
        class ExistingCursor:
            def execute(self, sql, params):
                self.sql = sql
                self.params = params
            def fetchone(self):
                return {'audit_id': 1, 'asset_domain': 'location_asset', 'asset_key': 'other'}
        event = {'operationId': 'id1', 'sourceSystem': 'sqlite:game1.db:location_asset_publications',
                 'sourceRecord': '1', 'assetDomain': 'location_asset', 'assetKey': 'tree_final'}
        with self.assertRaisesRegex(ValueError, 'different asset'):
            MySqlAssetReplacementAudit._append_with_cursor(None, ExistingCursor(), event, [], [])
