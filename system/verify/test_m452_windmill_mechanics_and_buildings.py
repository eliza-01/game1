"""M452: validated windmill tuning, authored socket contract and scoped migration."""
import json
import sqlite3
from contextlib import closing
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from options_store import OptionsStore, normalize_socket_ranges, normalize_rotations
from migrations.m452_buildings_keep_two import KEEP, RETIRE, migrate
from mechanics.catalog import snapshot, permitted_source


class WindmillOptionsM452(unittest.TestCase):
    def test_default_rotation_and_validation(self):
        self.assertEqual(normalize_rotations({})['windmill_02'],
                         {'enabled': True, 'secondsPerRevolution': 3.0})
        for update in ({'windmill_02': {'secondsPerRevolution': 0}},
                       {'windmill_02': {'secondsPerRevolution': float('inf')}},
                       {'windmill_02': {'secondsPerRevolution': True}},
                       {'windmill_02': {'enabled': 1}},
                       {'other': {'enabled': False}}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                normalize_rotations(update)

    def test_socket_range_upgrade_preserves_house_and_campfire(self):
        old = normalize_socket_ranges({'house': {'chest_01_socket': {'useRadius': 10}}})
        del old['windmill']
        new = normalize_socket_ranges({}, old)
        self.assertEqual(new['windmill']['windmill_door_handle_socket'], {'useRadius': 8})
        self.assertEqual(new['house']['chest_01_socket']['useRadius'], 10)
        self.assertEqual(new['campfire'], old['campfire'])
        self.assertEqual(normalize_socket_ranges({'windmill': {'windmill_door_handle_socket': {'useRadius': 11}}})
                         ['windmill']['windmill_door_handle_socket']['useRadius'], 11)
        for payload in ({'windmill': {'windmill_door_socket': {'useRadius': 8}}},
                        {'windmill': {'windmill_door_handle_socket': {'aimRadius': 4}}}):
            with self.assertRaises(ValueError): normalize_socket_ranges(payload)

    def test_options_persist_regenerate_and_upgrade(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = OptionsStore(root)
            old = store.snapshot()
            old['socketRanges'].pop('windmill')
            old.pop('rotations')
            store.manifest_path.write_text(json.dumps(old), encoding='utf-8')
            store = OptionsStore(root)
            self.assertEqual(store.snapshot()['socketRanges']['windmill']['windmill_door_handle_socket'],
                             {'useRadius': 8})
            saved = store.update({'rotations': {'windmill_02': {'secondsPerRevolution': 4.5}},
                                  'socketRanges': {'windmill': {'windmill_door_handle_socket': {'useRadius': 12}}}})
            self.assertEqual(saved['rotations']['windmill_02']['secondsPerRevolution'], 4.5)
            registry = store.registry_path.read_text(encoding='utf-8')
            self.assertIn('windmill_door_handle_socket', registry)
            self.assertIn('secondsPerRevolution = 4.5', registry)
            self.assertIn('useRadius = 12', registry)
            self.assertEqual(OptionsStore(root).snapshot()['socketRanges']['house'], saved['socketRanges']['house'])

    def test_mechanics_catalog_has_real_source_paths(self):
        domains = {row['id']: row for row in snapshot()['domains']}
        items = {row['id']: row for row in domains['windmill']['items']}
        self.assertEqual(items['windmill-02']['assetId'], 'windmill_02')
        for src in items['windmill-02']['sources']:
            self.assertIsNotNone(permitted_source('windmill-02', src['id']))
            self.assertTrue((ROOT / src['path']).is_file(), src['path'])


class BuildingsMigrationM452(unittest.TestCase):
    def test_unexpected_building_fails_before_any_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = root / '.control-center/game1.db'
            db.parent.mkdir(parents=True)
            with closing(sqlite3.connect(db)) as connection:
                connection.execute('CREATE TABLE location_assets(slug TEXT,category TEXT)')
                connection.executemany('INSERT INTO location_assets VALUES(?,?)',
                    [(slug,'building') for slug in (*KEEP, *RETIRE, 'other_building')])
                connection.commit()
            with self.assertRaisesRegex(ValueError, 'unreviewed building'):
                migrate(root)
            with closing(sqlite3.connect(db)) as connection:
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM location_assets').fetchone()[0], 6)
            self.assertFalse((root / '.control-center/backups').exists())


if __name__ == '__main__':
    unittest.main()
