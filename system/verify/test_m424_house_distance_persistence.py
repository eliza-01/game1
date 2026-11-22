"""Save through the HTTP adapter and reload using a new store/LOD Manager."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlsplit

from test_m414_house_part_distances import fixture, HOUSE
from test_location_lod_manager import Assets, Registry, PlaceRevisionStore
from real_estate.store import RealEstateStore
from services.location_lod_manager import LocationLodManager
from api.write_dispatch import dispatch_post
from api.read_world import route


class HouseDistancePersistence(unittest.TestCase):
    def test_save_and_fresh_overview_survive_reopening_database(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = RealEstateStore(root)
            fixture(store)
            from services.house_part_distances import ensure_schema
            ensure_schema(store)
            assets = Assets()
            def read():
                houses = RealEstateStore(root)
                registry = Registry(PlaceRevisionStore(root))
                manager = LocationLodManager(assets, registry, houses,
                    SimpleNamespace(snapshot=lambda: {'items': []}))
                with patch('services.location_lod_manager.build_catalog',
                           return_value={'digest': 'test', 'items': []}):
                    code, result = route(urlsplit('/api/lod-manager'),
                                         {'lod_manager': manager}, None)
                self.assertEqual(code, 200, result)
                return result['realEstate']['items'][0]['partStreaming']
            old = read()
            path = f'/api/real-estate/{HOUSE}/parts/roof/distances'
            payload = {'distances': {'lod1': 190, 'hide': 700}, 'expectedRevision': old['roof']['revision']}
            status, reply = dispatch_post(path, lambda: payload, {'real_estate': store})
            self.assertEqual(status, 200, reply)
            self.assertEqual(reply['distances']['hide'], 700)
            fresh = read()
            self.assertEqual(fresh['roof'], reply['distances'])
            self.assertEqual(fresh['walls_outside'], old['walls_outside'])
            status, _ = dispatch_post(path, lambda: payload, {'real_estate': store})
            self.assertEqual(status, 400)
            self.assertEqual(read(), fresh)

    def test_unloaded_priority_persists_corrected_thresholds(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = RealEstateStore(root)
            fixture(store)
            from services.house_part_distances import ensure_schema, normalize_edit, validate
            ensure_schema(store)
            other = store.get(HOUSE)['partStreaming']['walls_outside']
            path = f'/api/real-estate/{HOUSE}/parts/roof/distances'
            for revision, (lod1, hide, expected) in enumerate([
                (150, 100, (79, 100)), (50, 40, (20, 41)),
                (20, 41, (20, 41)), (150, 400, (150, 400)),
                (9999, 10000, (9979, 10000)), (50, 70, (49, 70)),
            ], start=1):
                payload = {'distances': {'lod1': lod1, 'hide': hide}, 'expectedRevision': revision}
                status, reply = dispatch_post(path, lambda: payload, {'real_estate': store})
                self.assertEqual(status, 200, reply)
                row = RealEstateStore(root).get(HOUSE)['partStreaming']['roof']
                self.assertEqual(row, reply['distances'])
                self.assertEqual((row['lod1'], row['hide']), expected)
                self.assertEqual(row['revision'], revision+1)
                validate({key: row[key] for key in ('lod1', 'hide')})
            for bad in [{'lod1': 50, 'hide': 0}, {'lod1': 50, 'hide': 10001},
                        {'lod1': True, 'hide': 40}, {'lod1': 19, 'hide': 100},
                        {'lod1': 50, 'hide': 40.5}]:
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    normalize_edit(bad)
            self.assertEqual(store.get(HOUSE)['partStreaming']['walls_outside'], other)
