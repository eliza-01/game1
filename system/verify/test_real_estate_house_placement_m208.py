"""M208 authoring contract: independent plot/house, Studio-only measurement."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
import sqlite3
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system' / 'control-center'))
from real_estate.placement import RealEstatePlacementStore, validate_capture
from api import real_estate as real_estate_api


def cf(x=0, y=0, z=0):
    return [x, y, z, 1, 0, 0, 0, 1, 0, 0, 0, 1]


def capture(slug='house_level3_01', plot=39, scale=1.25):
    return {'schemaVersion': 1, 'houseSlug': slug, 'plotIndex': plot,
            'plotVolume': f'plot_{plot:02d}_volume',
            'worldCFrame': cf(100, 5, -34), 'plotCFrame': cf(95, 0, -40),
            'localCFrame': cf(5, 5, 6), 'scale': scale}


class Houses:
    def __init__(self, slugs):
        self.slugs = slugs

    def get(self, slug):
        return {'slug': slug} if slug in self.slugs else None


class PlacementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        db = self.root / '.control-center' / 'game1_real_estate.db'
        db.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db) as connection:
            connection.execute('CREATE TABLE real_estate (slug TEXT PRIMARY KEY)')
            connection.executemany('INSERT INTO real_estate VALUES (?)',
                                   [('house_level3_01',), ('house_level5_01',)])
        self.houses = Houses({'house_level3_01', 'house_level5_01'})
        self.store = RealEstatePlacementStore(self.root, self.houses)

    def test_bind_multiple_house_sizes_and_plots(self):
        first = self.store.bind('house_level3_01', 39, capture())
        self.assertEqual(first['revision'], 1)
        self.store.bind('house_level5_01', 39, capture('house_level5_01', 39, .85))
        self.store.bind('house_level3_01', 1, capture('house_level3_01', 1))
        second = self.store.bind('house_level3_01', 39, capture(scale=2))
        self.assertEqual(second['revision'], 2)
        self.assertEqual(second['scale'], 2)
        self.assertEqual(len(self.store.snapshot()['items']), 3)
        self.assertEqual([x['localCFrame'][:3] for x in self.store.snapshot()['items']],
                         [[5, 5, 6]] * 3)
        # Connections are closed: a brand-new repository can reopen and read it.
        reopened = RealEstatePlacementStore(self.root, self.houses)
        self.assertEqual(len(reopened.snapshot()['items']), 3)
        manifest = json.loads((self.root / 'assets/manifests/real-estate-placements.json').read_text())
        self.assertEqual(manifest['items'], reopened.snapshot()['items'])
        self.assertEqual(manifest['schemaVersion'], 1)

    def test_invalid_capture_never_modifies_existing_record(self):
        good = self.store.bind('house_level3_01', 39, capture())
        for broken in (
            {**capture(), 'houseSlug': 'house_level5_01'},
            {**capture(), 'plotIndex': 40},
            {**capture(), 'scale': float('nan')},
            {**capture(), 'worldCFrame': cf()[:-1]},
            {**capture(), 'localCFrame': cf(999, 5, 6)},
            {**capture(), 'worldCFrame': cf()[:3] + [1,0,0,0,0,0,0,0,1]},
        ):
            with self.subTest(broken=broken), self.assertRaises(ValueError):
                self.store.bind('house_level3_01', 39, broken)
        self.assertEqual(self.store.snapshot()['items'], [good])
        with self.assertRaises(ValueError):
            self.store.bind('unregistered', 39, capture('unregistered'))
        for invalid in (0, 51, 1.5, True):
            with self.subTest(plot=invalid), self.assertRaises(ValueError):
                self.store.bind('house_level3_01', invalid, capture())

    def test_plot_relative_rotation_is_preserved(self):
        # 90-degree rotation around Y: local +X maps toward world -Z.
        turn = [0, 0, 1, 0, 1, 0, -1, 0, 0]
        authored = capture()
        authored['plotCFrame'] = [95, 0, -40] + turn
        authored['worldCFrame'] = [101, 5, -45] + turn
        stored = self.store.bind('house_level3_01', 39, authored)
        self.assertEqual(stored['worldCFrame'], authored['worldCFrame'])
        self.assertEqual(stored['plotCFrame'], authored['plotCFrame'])
        self.assertEqual(stored['localCFrame'], authored['localCFrame'])

    def test_deleting_house_retires_only_its_bindings(self):
        self.store.bind('house_level3_01', 39, capture())
        self.store.bind('house_level5_01', 39, capture('house_level5_01'))
        with sqlite3.connect(self.store.db) as connection:
            connection.execute("DELETE FROM real_estate WHERE slug='house_level3_01'")
        self.store.export()
        self.assertEqual([x['houseSlug'] for x in self.store.snapshot()['items']],
                         ['house_level5_01'])

    def test_route_captures_studio_not_browser_transform(self):
        calls = []
        def studio(slug, plot):
            calls.append((slug, plot))
            return capture(slug, plot)
        deps = {'real_estate': self.houses, 'real_estate_placements': self.store,
                'capture_house_placement': studio}
        status, result = real_estate_api.write('/api/real-estate/placements/bind',
            lambda: {'houseSlug': 'house_level3_01', 'plotIndex': 39,
                     'worldCFrame': cf(999)}, deps)
        self.assertEqual(status, 200)
        self.assertEqual(calls, [('house_level3_01', 39)])
        self.assertEqual(result['item']['worldCFrame'][0], 100)
        status, result = real_estate_api.write('/api/real-estate/placements/bind',
            lambda: {'houseSlug': 'house_level3_01', 'plotIndex': 51}, deps)
        self.assertEqual(status, 400)
        self.assertEqual(len(calls), 1)

    def test_studio_integration_is_bundled_and_edit_mode_only(self):
        plugin = ROOT / 'system/studio-plugin'
        manifest = json.loads((plugin / 'plugin.project.json').read_text())
        self.assertEqual(manifest['tree']['modules']['StudioHousePlacementCapture']['$path'],
                         'modules/StudioHousePlacementCapture.luau')
        source = (plugin / 'modules/StudioHousePlacementCapture.luau').read_text()
        entry = (plugin / 'Game1Bridge.server.luau').read_text()
        for needle in ('Selection:Get()', 'RunService:IsRunning()', 'PlotsCatalog.Collect(Workspace)',
                       'model:GetPivot()', 'model:GetScale()', 'plotFrame:ToObjectSpace(world)'):
            self.assertIn(needle, source)
        self.assertIn('handleHousePlacementCapture(data)', entry)


if __name__ == '__main__':
    unittest.main()

class PlacementBridgeTests(unittest.TestCase):
    def test_studio_capture_response_identity_and_measured_transform(self):
        import threading
        import time
        from urllib.request import Request, urlopen
        from services.studio_house_placement_bridge import capture_house_placement

        errors = []
        def studio():
            try:
                from studio_bridge import PORT, TOKEN
                base = f'http://127.0.0.1:{PORT}'
                command = None
                for _ in range(100):
                    try:
                        request = Request(base + '/command', headers={'X-Game1-Token': TOKEN})
                        with urlopen(request, timeout=2) as response:
                            command = json.load(response)
                        break
                    except OSError:
                        time.sleep(.025)
                if command is None:
                    raise AssertionError('Studio never received bridge command')
                result = {**command, **capture(command['houseSlug'], command['plotIndex'])}
                post = Request(base + '/house-placement-result',
                               data=json.dumps(result).encode('utf-8'), method='POST',
                               headers={'X-Game1-Token': TOKEN, 'Content-Type':'application/json'})
                with urlopen(post, timeout=2) as response:
                    self.assertEqual(response.status, 200)
            except Exception as exc:
                errors.append(exc)
        worker = threading.Thread(target=studio, daemon=True)
        worker.start()
        try:
            result = capture_house_placement('house_level3_01', 39, timeout_seconds=4)
        finally:
            worker.join(timeout=5)
        self.assertEqual(errors, [])
        self.assertEqual(result['worldCFrame'][:3], [100, 5, -34])
        self.assertEqual(result['localCFrame'][:3], [5, 5, 6])
