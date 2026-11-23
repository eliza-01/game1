"""M452 one-shot migration and runtime Options contract regression."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import sqlite3
from contextlib import closing
import sys
from tempfile import TemporaryDirectory
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from options_store import OptionsStore, normalize_rotations
from sqlite_connection import connect as connect_sqlite

spec = importlib.util.spec_from_file_location('m452_migration',
    ROOT / 'system/control-center/migrations/m452_buildings_keep_two.py')
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


class RotationContractTests(unittest.TestCase):
    def test_speed_and_enabled_are_validated(self):
        self.assertEqual(normalize_rotations({})['windmill_02']['secondsPerRevolution'], 3.0)
        self.assertEqual(normalize_rotations({'windmill_02': {'enabled': False}})['windmill_02']['enabled'], False)
        for bad in (0, -1, 200, float('nan'), float('inf'), True):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                normalize_rotations({'windmill_02': {'secondsPerRevolution': bad}})
        with self.assertRaises(ValueError):
            normalize_rotations({'windmill_01': {'enabled': True}})

    def test_saved_settings_generate_roblox_registry(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            options = OptionsStore(root)
            saved = options.update({'rotations': {'windmill_02': {
                'enabled': False, 'secondsPerRevolution': 5.5,
            }}})
            self.assertEqual(saved['rotations']['windmill_02']['secondsPerRevolution'], 5.5)
            rendered = (root / 'src/shared/GameOptionsRegistry.luau').read_text(encoding='utf-8')
            self.assertIn('rotations = table.freeze', rendered)
            self.assertIn('secondsPerRevolution = 5.5', rendered)
            self.assertIn('enabled = false', rendered)
            self.assertEqual(OptionsStore(root).snapshot()['rotations'], saved['rotations'])


class _StubStore:
    def __init__(self, root):
        self.root = root
    def connect(self):
        return connect_sqlite(self.root / '.control-center/game1.db')
    def delete(self, slug):
        with closing(self.connect()) as conn:
            conn.execute('DELETE FROM location_assets WHERE slug=?', (slug,))
            conn.commit()
        archive = self.root / '.control-center/location-assets-retired'
        archive.mkdir(parents=True, exist_ok=True)
        (archive / (slug + '.json')).write_text('{}', encoding='utf-8')
        return {'archived': (archive / (slug + '.json')).relative_to(self.root).as_posix()}
    def export(self):
        pass


class MigrationTests(unittest.TestCase):
    def _fixture(self, root, extra=None):
        db = root / '.control-center/game1.db'
        db.parent.mkdir(parents=True)
        with closing(sqlite3.connect(db)) as conn:
            conn.execute('CREATE TABLE location_assets(slug TEXT PRIMARY KEY,category TEXT,model_asset_id TEXT)')
            conn.execute('CREATE TABLE location_asset_slug_aliases(old_slug TEXT,current_slug TEXT)')
            for slug in ('smithy_01','windmill_02','smithy','windmill_01','weapon_shop'):
                conn.execute('INSERT INTO location_assets VALUES(?,?,?)',
                    (slug, 'building', '86999805819635' if slug == 'windmill_02' else slug))
            conn.execute('INSERT INTO location_assets VALUES(?,?,?)', ('tree_01','tree','tree'))
            if extra:
                conn.execute('INSERT INTO location_assets VALUES(?,?,?)', (extra,'building','x'))
            conn.execute('INSERT INTO location_asset_slug_aliases VALUES(?,?)', ('old_windmill','windmill_01'))
            conn.execute('INSERT INTO location_asset_slug_aliases VALUES(?,?)', ('old_tree','tree_01'))
            conn.commit()
        return db

    def test_migration_keeps_ids_and_other_categories_with_backup(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = self._fixture(root)
            with patch.dict(sys.modules, {'location_asset_store': types.SimpleNamespace(LocationAssetStore=_StubStore)}):
                result = module.migrate(root)
                again = module.migrate(root)
            self.assertTrue(result['ok'])
            self.assertTrue(again['alreadyMigrated'])
            with closing(sqlite3.connect(db)) as conn:
                buildings = conn.execute("SELECT slug,model_asset_id FROM location_assets WHERE category='building' ORDER BY slug").fetchall()
                self.assertEqual(buildings, [('smithy_01','smithy_01'),('windmill_02','86999805819635')])
                self.assertEqual(conn.execute("SELECT slug FROM location_assets WHERE category='tree'").fetchone(), ('tree_01',))
                self.assertEqual(conn.execute("SELECT current_slug FROM location_asset_slug_aliases").fetchall(), [('tree_01',)])
            backup = root / result['backup'] / 'game1.db'
            with closing(sqlite3.connect(backup)) as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM location_assets WHERE category='building'").fetchone()[0], 5)

    def test_unknown_asset_fails_closed(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = self._fixture(root, 'user_new_building')
            with self.assertRaisesRegex(ValueError, 'unreviewed building'):
                module.migrate(root)
            with closing(sqlite3.connect(db)) as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM location_assets WHERE category='building'").fetchone()[0], 6)


if __name__ == '__main__':
    unittest.main()
