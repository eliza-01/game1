"""M230: 39 pre-M229 plot bindings stay usable without fabricated anchor data."""
from __future__ import annotations
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from sqlite_connection import connect
from real_estate.placement import RealEstatePlacementStore
from services.studio_house_placement_bridge import bulk_house_placements, preview_house_placement


def cf(x=0):
    return [x, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1]


class LegacyPlacementM230(TestCase):
    def test_all_thirty_nine_legacy_bindings_survive_and_remain_placeable(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            db = root/'.control-center/game1_real_estate.db'
            db.parent.mkdir(parents=True)
            with connect(db) as sql:
                sql.execute('CREATE TABLE real_estate (slug TEXT PRIMARY KEY)')
                sql.execute("INSERT INTO real_estate VALUES ('house_level3_01')")
            store = RealEstatePlacementStore(root, mock.Mock(get=lambda slug: {'slug': slug}))
            # Insert with the normal persisted schema; these are legitimate M208 bindings.
            with connect(db) as sql:
                for plot in range(1, 40):
                    sql.execute("""INSERT INTO real_estate_placements (
                        plot_index, house_slug, plot_volume, world_cframe_json,
                        plot_cframe_json, local_cframe_json, model_scale,
                        revision, anchored, updated_at, house_anchor_local_cframe_json)
                        VALUES (?, 'house_level3_01', ?, ?, ?, ?, 1, 1, 1, 1, NULL)""",
                        (plot, f'plot_{plot:02d}_volume',
                         json.dumps(cf(plot)), json.dumps(cf()), json.dumps(cf(plot))))
            bindings = store.snapshot()['items']
            self.assertEqual(len(bindings), 39)
            self.assertTrue(all(row['houseAnchorLocalCFrame'] is None for row in bindings))
            before = [(row['plotIndex'], row['localCFrame'], row['worldCFrame'], row['revision'])
                      for row in bindings]
            with mock.patch('services.studio_house_placement_bridge._request_house_placement') as request:
                request.return_value = {'status': 'placed_all', 'changed': 39,
                                        'anchoredPartsVerified': 39, 'legacyPlacements': 39}
                result = bulk_house_placements('house_level3_01', 'place_all', bindings)
                self.assertEqual(result['changed'], 39)
                sent = request.call_args.kwargs['targets']
                self.assertEqual(len(sent), 39)
                self.assertTrue(all(row['houseAnchorLocalCFrame'] is None for row in sent))
            after = [(row['plotIndex'], row['localCFrame'], row['worldCFrame'], row['revision'])
                     for row in store.snapshot()['items']]
            self.assertEqual(before, after)

    def test_ui_uses_plot_local_pivot_and_independent_house_type(self):
        source = (ROOT/'system/control-center/static/real-estate-placement.js').read_text(encoding='utf-8')
        self.assertIn("const validType=/^house_level", source)
        self.assertIn("const canPlace=Array.isArray(item.localCFrame)", source)
        self.assertIn("re-placement-house-options", source)
        self.assertNotIn("Legacy Model pivot", source)

    def test_studio_places_republished_model_by_plot_pivot(self):
        studio = (ROOT/'system/studio-plugin/modules/StudioHousePlacementPreview.luau').read_text(encoding='utf-8')
        router = (ROOT/'system/studio-plugin/Game1Bridge.server.luau').read_text(encoding='utf-8')
        bridge = (ROOT/'system/control-center/services/studio_house_placement_bridge.py').read_text(encoding='utf-8')
        self.assertIn('clone:PivotTo(desiredRoot)', studio)
        self.assertIn('Game1PlacementRotationMode", "plot-author-pivot"', studio)
        self.assertIn('house-placement-preview-v4', studio)
        self.assertIn('house-placement-preview-v4', router)
        self.assertIn('house-placement-preview-v4', bridge)

    def test_new_and_legacy_bindings_can_coexist_in_one_batch(self):
        legacy = {'houseSlug': 'house_a', 'plotIndex': 1, 'anchored': False,
                  'localCFrame': cf(1), 'houseAnchorLocalCFrame': None}
        exact = {'houseSlug': 'house_a', 'plotIndex': 2, 'anchored': True,
                 'localCFrame': cf(2), 'houseAnchorLocalCFrame': cf()}
        with mock.patch('services.studio_house_placement_bridge._request_house_placement') as request:
            request.return_value = {'status': 'placed_all', 'changed': 2,
                                    'anchoredPartsVerified': 5, 'legacyPlacements': 1}
            result = bulk_house_placements('house_a', 'place_all', [exact, legacy])
            self.assertEqual(result['legacyPlacements'], 1)
            self.assertEqual(request.call_args.kwargs['targets'], [legacy, exact])
