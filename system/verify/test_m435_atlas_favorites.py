"""M435: one persisted favorite priority for every Atlas Registry consumer."""
from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from api.write_world import route
from sqlite_connection import connect as connect_sqlite
from services.texture_atlas_registry import AtlasRegistry
from services.npc_atlas_sources import NpcAtlasSources


class StubList:
    def __init__(self, rows, atlases=None):
        self.rows = rows
        self.atlases = atlases

    def list(self):
        return self.rows


class AtlasFavoritesM435(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix='m435-atlas-favorite-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / '.control-center').mkdir()
        self.registry = AtlasRegistry(self.root)
        self.a = self.register('test_a_64x64_atlas.png', 64)
        self.b = self.register('test_b_128x128_atlas.png', 128)
        with self.registry.connect() as db:
            for v, published in ((self.a, '91001'), (self.b, '91002')):
                db.execute('UPDATE texture_atlas_variants SET published_id=?,published_sha256=source_sha256 WHERE id=?',
                           (published, v['id']))
        self.registry.bind('location_asset', 'item', self.a['id'])

    def register(self, filename, size):
        image = self.root / 'incoming' / filename
        image.parent.mkdir(exist_ok=True)
        Image.new('RGBA', (size, size), 'red').save(image)
        return self.registry.register_file(str(image))

    def test_favorite_persists_across_restart_and_all_catalogs(self):
        before = self.registry.binding('location_asset', 'item')
        self.assertFalse(self.registry.get_variant(self.b['id'])['favorite'])
        self.assertTrue(self.registry.set_favorite(self.b['id'], True)['favorite'])
        self.assertTrue(self.registry.set_favorite(self.b['id'], True)['favorite'])  # idempotent
        reopened = AtlasRegistry(self.root)
        self.assertTrue(reopened.get_variant(self.b['id'])['favorite'])
        self.assertTrue(next(v for f in reopened.catalog() for v in f['variants'] if v['id'] == self.b['id'])['favorite'])
        self.assertTrue(next(v for f in reopened.catalog_with_consumers() for v in f['variants'] if v['id'] == self.b['id'])['favorite'])
        after = reopened.binding('location_asset', 'item')
        self.assertEqual(before['variant_id'], after['variant_id'])
        self.assertEqual(before['revision'], after['revision'])
        self.assertEqual(before['published_id'], after['published_id'])
        self.assertFalse(after['favorite'])
        self.assertTrue(reopened.set_favorite(self.a['id'], True)['favorite'])
        self.assertTrue(reopened.binding('location_asset', 'item')['favorite'])
        self.assertEqual(reopened.binding('location_asset', 'item')['revision'], before['revision'])
        self.assertFalse(reopened.set_favorite(self.b['id'], False)['favorite'])
        self.assertFalse(AtlasRegistry(self.root).get_variant(self.b['id'])['favorite'])

    def test_http_requires_explicit_bool_and_does_not_change_binding(self):
        keys = ('deco_layouts location_assets locations monster_spawns npc_place_spawn '
                'npc_register_spawn npc_spawns options_store publication_credentials '
                'request_active_studio_save run_timeline_editor_bridge sync_monster_to_studio timelines').split()
        deps = dict.fromkeys(keys)
        deps['location_assets'] = SimpleNamespace(atlases=self.registry)
        uri = f'/api/texture-atlases/variants/{self.a["id"]}/favorite'
        for payload in ({'favorite': 'true'}, {'favorite': 1}, {}, {'favorite': True, 'unexpected': 1}):
            status, _ = route(uri, lambda: payload, deps)
            self.assertEqual(status, 400)
        status, result = route(uri, lambda: {'favorite': True}, deps)
        self.assertEqual(status, 200)
        self.assertTrue(result['variant']['favorite'])
        self.assertEqual(self.registry.binding('location_asset', 'item')['revision'], 1)
        status, _ = route('/api/texture-atlases/variants/999999/favorite', lambda: {'favorite': True}, deps)
        self.assertEqual(status, 400)

    def test_npc_reuse_inherits_favorite_without_reupload(self):
        v = self.registry.set_favorite(self.b['id'], True)
        npc = StubList([])
        location = StubList([
            {'slug': 'alpha', 'name_en': 'Alpha', 'atlasVariantId': self.a['id']},
            {'slug': 'zeta', 'name_en': 'Zeta', 'atlasVariantId': self.b['id']},
        ], self.registry)
        service = NpcAtlasSources(npc, StubList([]), StubList([]), location, StubList([]))
        rows = service.snapshot()['groups']['location_asset']
        self.assertEqual([r['slug'] for r in rows], ['zeta', 'alpha'])
        self.assertEqual([r['favorite'] for r in rows], [True, False])
        self.assertEqual(rows[0]['imageId'], v['published_id'])

    def test_additive_migration_on_existing_database_copy(self):
        original = ROOT / '.control-center' / 'game1.db'
        if not original.is_file():
            self.skipTest('real authoring database is not part of this distribution')
        separate = self.root / 'real-copy'
        (separate / '.control-center').mkdir(parents=True)
        copied = separate / '.control-center' / 'game1.db'
        # SQLite online backup produces a consistent fixture even if Control Center
        # is using the original database (or has uncheckpointed WAL changes).
        with connect_sqlite(original) as source, connect_sqlite(copied) as target:
            source.backup(target)
        with connect_sqlite(copied) as db:
            before = [(row['id'], row['published_id']) for row in db.execute(
                'SELECT id,published_id FROM texture_atlas_variants ORDER BY id')]
            # Simulate an actual pre-M435 database. An installed M435 database
            # already has this table and must NOT create another backup on reopen.
            # Drop only in the temporary snapshot, never in the authoring database.
            db.execute('DROP TABLE IF EXISTS texture_atlas_favorites')

        AtlasRegistry(separate)
        with connect_sqlite(copied) as db:
            after = [(row['id'], row['published_id']) for row in db.execute(
                'SELECT id,published_id FROM texture_atlas_variants ORDER BY id')]
            self.assertEqual(before, after)  # includes retired/history variants
            self.assertIsNotNone(db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='texture_atlas_favorites'").fetchone())
        backup_dir = separate / '.control-center' / 'backups'
        backups = sorted(backup_dir.glob('before_atlas_favorites_m435_*.db'))
        self.assertEqual(len(backups), 1 if before else 0)
        if before:
            with connect_sqlite(backups[0]) as saved:
                saved_rows = [(row['id'], row['published_id']) for row in saved.execute(
                    'SELECT id,published_id FROM texture_atlas_variants ORDER BY id')]
                self.assertIsNone(saved.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='texture_atlas_favorites'").fetchone())
            self.assertEqual(saved_rows, before)
        # Idempotence: reopening the migrated database must not make a new backup.
        AtlasRegistry(separate)
        self.assertEqual(sorted(backup_dir.glob('before_atlas_favorites_m435_*.db')), backups)
