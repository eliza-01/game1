"""One saved profile per Location slug; a shared band across both runtime domains."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from test_location_runtime_build import fixture
from test_location_lod_manager import Assets, Registry, PlaceRevisionStore
from test_m414_house_part_distances import fixture as house_fixture, HOUSE
from real_estate.store import RealEstateStore
from services.house_part_distances import ensure_schema
from services.location_streaming_config import LocationStreamingConfig, DEFAULT_SETTINGS
from services.location_lod_manager import LocationLodManager
from services.location_runtime_build import _runtime_payload
from services.lod_studio_preview import snapshot


class IndividualDistances(unittest.TestCase):
    def test_migrate_and_isolate_profiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = LocationStreamingConfig(tmp)
            config.path.parent.mkdir()
            old = {'schemaVersion': 1, 'modes': {'stone_fence_02': 'lod1'},
                   'distances': {'lod1': 120, 'lod2': 260, 'hide': 300, 'hysteresis': 12},
                   'workspace': copy.deepcopy(DEFAULT_SETTINGS['workspace'])}
            config.path.write_text(json.dumps(old))
            slugs = ['stone_fence_02', 'stone_pillar_03', 'no_placement']
            data = config.read(slugs)
            self.assertEqual(data['schemaVersion'], 2)
            self.assertEqual(data['hysteresis'], 12)
            self.assertNotIn('distances', data)
            self.assertEqual(set(data['assetDistances']), set(slugs))
            self.assertTrue(all(p['hide'] == 300 for p in data['assetDistances'].values()))
            config.save({'assetDistances': {'stone_fence_02': {'lod1': 150, 'lod2': 250, 'hide': 100}}}, slugs)
            latest = LocationStreamingConfig(tmp).read(slugs + ['new_asset'])
            self.assertEqual(latest['assetDistances']['stone_fence_02'], {'lod1': 75, 'lod2': 250, 'hide': 100})
            self.assertEqual(latest['assetDistances']['stone_pillar_03']['hide'], 300)
            self.assertEqual(latest['assetDistances']['new_asset']['hide'], 400)
            before = config.path.read_bytes()
            with self.assertRaises(ValueError):
                config.save({'assetDistances': {'stone_fence_02': {'lod1':1,'lod2':2,'hide':3,'hysteresis':5}}}, slugs)
            self.assertEqual(config.path.read_bytes(), before)

    def test_shared_band_live_preview_and_compiler(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            houses = RealEstateStore(root)
            house_fixture(houses)
            ensure_schema(houses)
            manager = LocationLodManager(Assets(), Registry(PlaceRevisionStore(root)), houses)
            first = snapshot(manager)
            manager.save_settings({'modes': {'stone_fence_02':'lod1','wooden_fence_01':'full'},
                'assetDistances': {'stone_fence_02': {'lod1':120,'lod2':260,'hide':100},
                                   'wooden_fence_01': {'lod1':120,'lod2':260,'hide':50}}, 'hysteresis':12})
            houses.save_part_distances(HOUSE, 'roof', {'lod1':50,'hide':40}, 1)
            later = snapshot(manager)
            self.assertNotEqual(later['digest'], first['digest'])
            self.assertEqual(later['hysteresis'],12)
            self.assertEqual(later['locations']['stone_fence_02']['distances']['lod1'],75)
            self.assertEqual(later['locations']['wooden_fence_01']['distances']['hide'],50)
            self.assertEqual(later['houses'][HOUSE]['parts']['roof']['hide'],45)
            self.assertEqual(later['locations']['no_placement'],first['locations']['no_placement'])
            manager.save_settings({'hysteresis':30})
            updated = snapshot(manager)
            self.assertEqual(updated['hysteresis'],30)
            self.assertEqual(updated['houses'][HOUSE]['parts']['roof']['hide'],92)
            self.assertEqual(updated['locations']['stone_fence_02']['distances']['lod1'],39)
            self.assertEqual(updated['locations']['wooden_fence_01']['distances']['hide'],50)
            _, rows = fixture(root)
            payload = _runtime_payload(rows, snapshot_id=1, catalog_digest='test',settings=manager.read_settings())
            self.assertEqual(payload['hysteresis'],30)
            self.assertEqual(payload['assetDistances']['stone_fence_02'],updated['locations']['stone_fence_02']['distances'])
            self.assertNotIn('distances',payload)
            self.assertEqual(set(payload['assetDistances']),set(payload['targets']))
