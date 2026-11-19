"""M373: saved plot spawn pivots outlive any house publication or model."""
from __future__ import annotations
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'system/control-center'))
from sqlite_connection import connect
from real_estate.placement import RealEstatePlacementStore


def cf(x=0, y=0, z=0):
    return [x, y, z, 1, 0, 0, 0, 1, 0, 0, 0, 1]


def captured(slug, plot=1):
    return {'schemaVersion': 2, 'houseSlug': slug, 'plotIndex': plot,
        'plotVolume': f'plot_{plot:02d}_volume', 'worldCFrame': cf(15, 0, 6),
        'plotCFrame': cf(10, 0, 0), 'localCFrame': cf(5, 0, 6),
        'houseAnchorLocalCFrame': cf(), 'houseAnchorWorldCFrame': cf(15, 0, 6),
        'scale': 1.0}

class Registry:
    def get(self, slug):
        return None  # no registered model is necessary to retain plot pivots


class M373PlotPivots(unittest.TestCase):
    def test_delete_then_re_register_preserves_pivot_and_revision(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            db = root/'.control-center'/'game1_real_estate.db'
            db.parent.mkdir(parents=True)
            with connect(db) as c:
                c.execute('CREATE TABLE real_estate (slug TEXT PRIMARY KEY, model_asset_id TEXT)')
                c.execute("INSERT INTO real_estate VALUES ('house_level5_01', 'old-model')")
                c.execute('''CREATE TABLE real_estate_placements (
                    plot_index INTEGER, house_slug TEXT, plot_volume TEXT,
                    world_cframe_json TEXT, plot_cframe_json TEXT, local_cframe_json TEXT,
                    model_scale REAL, revision INTEGER, anchored INTEGER,
                    house_anchor_local_cframe_json TEXT, updated_at REAL,
                    PRIMARY KEY(plot_index, house_slug))''')
                c.execute('''CREATE TRIGGER real_estate_placements_house_delete
                    AFTER DELETE ON real_estate BEGIN
                    DELETE FROM real_estate_placements WHERE house_slug=OLD.slug;
                    END''')
            store = RealEstatePlacementStore(root, Registry())
            self.assertEqual(len(list((db.parent/'backups').glob('before_independent_plot_pivots_m373_*.db'))), 1)
            row = store.bind('house_level5_01', 1, captured('house_level5_01'))
            with connect(db) as c:
                c.execute("DELETE FROM real_estate WHERE slug='house_level5_01'")
            self.assertEqual(store.get('house_level5_01', 1), row)
            self.assertEqual(store.snapshot()['items'][0]['spawnPivotLocalCFrame'], cf(5, 0, 6))
            self.assertEqual(store.snapshot()['items'][0]['houseVariant'], '01')
            with connect(db) as c:
                c.execute("INSERT INTO real_estate VALUES ('house_level5_01', 'new-model')")
            self.assertEqual(store.get('house_level5_01', 1), row)
            reopened = RealEstatePlacementStore(root, Registry())
            self.assertEqual(reopened.get('house_level5_01', 1), row)
            self.assertEqual(len(list((db.parent/'backups').glob('before_independent_plot_pivots_m373_*.db'))), 1)
            manifest = json.loads((root/'assets/manifests/real-estate-placements.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['items'][0]['houseLevel'], 5)

    def test_plot_can_be_bound_without_currently_registered_house(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'.control-center').mkdir()
            store = RealEstatePlacementStore(root, Registry())
            row = store.bind('house_level1_01', 3, captured('house_level1_01', 3))
            self.assertEqual(row['houseLevel'], 1)
            self.assertEqual(row['spawnPivotLocalCFrame'], cf(5, 0, 6))
            with self.assertRaises(ValueError):
                store.bind('random_deleted_asset_id', 3, captured('random_deleted_asset_id', 3))

    def test_live_contracts_use_authored_model_pivots_and_new_sockets(self):
        def text(path): return (ROOT/path).read_text(encoding='utf-8')
        preview = text('system/studio-plugin/modules/StudioHousePlacementPreview.luau')
        capture = text('system/studio-plugin/modules/StudioHousePlacementCapture.luau')
        policy = text('src/shared/world/HouseElevatorPolicy.luau')
        contract = text('src/shared/world/HouseSocketContract.luau')
        self.assertIn('clone:PivotTo(desiredRoot)', preview)
        self.assertIn('local world = model:GetPivot()', capture)
        self.assertNotIn('FindUniqueNamed(root,"house")', text('system/studio-plugin/modules/StudioRealEstateHouseFrame.luau'))
        self.assertIn('house_floor_%02d_spawn_socket', policy)
        self.assertIn('house_floor_01_spawn_socket', contract)
        self.assertIn('door_01_padlock_01_inside_socket', contract)
        self.assertIn('houseplant_%03d', contract)  # authored names houseplant_010..015
        self.assertIn('houseplant_%02d', contract)  # authored names houseplant_01..09
        self.assertNotIn('"land_spawn_01_socket"', contract)
        self.assertNotIn('house_floor_01_spawn_01_socket', contract)
        self.assertIn('Contract.HasPadlock(entry.sockets)',text('src/server/world/HouseSocketService.luau'))
        self.assertIn('re-placement-house-options', text('system/control-center/static/index.html'))
        self.assertIn('const validType=', text('system/control-center/static/real-estate-placement.js'))

if __name__ == '__main__':
    unittest.main()
