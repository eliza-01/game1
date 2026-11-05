"""M229 -- capture author house anchor; refuse uncalibrated preview placements."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from real_estate.placement import RealEstatePlacementStore, validate_capture
from services.studio_house_placement_bridge import preview_house_placement, bulk_house_placements


def frame(x=0, y=0, z=0, rotation=None):
    return [x, y, z] + (rotation or [1, 0, 0, 0, 1, 0, 0, 0, 1])


def sample_capture():
    # Model rotated 90 degrees relative to world; house pivot is rotated
    # a further 90 degrees, so relying on wrapper Model pivot loses a turn.
    yaw90 = [0, 0, 1, 0, 1, 0, -1, 0, 0]
    yaw180 = [-1, 0, 0, 0, 1, 0, 0, 0, -1]
    return {
        'schemaVersion': 2, 'houseSlug': 'house_a', 'plotIndex': 1,
        'plotVolume': 'plot_01_volume', 'plotCFrame': frame(),
        'localCFrame': frame(10, 0, 0, yaw90),
        'worldCFrame': frame(10, 0, 0, yaw90),
        'houseAnchorLocalCFrame': frame(0, 0, 0, yaw90),
        'houseAnchorWorldCFrame': frame(10, 0, 0, yaw180),
        'scale': 1.25,
    }


class PlacementRotationM229(TestCase):
    def setUp(self):
        t = TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        db = self.root / '.control-center/game1_real_estate.db'
        db.parent.mkdir()
        with sqlite3.connect(db) as connection:
            connection.execute('CREATE TABLE real_estate (slug TEXT PRIMARY KEY)')
            connection.execute("INSERT INTO real_estate VALUES ('house_a')")
        self.store = RealEstatePlacementStore(self.root, mock.Mock(get=lambda slug: {'slug': slug}))

    def test_nonzero_rotation_captured_and_exported(self):
        captured = sample_capture()
        stored = self.store.bind('house_a', 1, captured)
        self.assertEqual(stored['houseAnchorLocalCFrame'], captured['houseAnchorLocalCFrame'])
        self.assertEqual(stored['worldCFrame'], captured['worldCFrame'])
        self.assertEqual(stored['revision'], 1)
        self.assertEqual(self.store.get('house_a', 1)['houseAnchorLocalCFrame'], captured['houseAnchorLocalCFrame'])
        manifest = json.loads((self.root/'assets/manifests/real-estate-placements.json').read_text())
        self.assertEqual(manifest['items'][0]['houseAnchorLocalCFrame'], captured['houseAnchorLocalCFrame'])
        self.assertEqual(self.store.bind('house_a', 1, captured)['revision'], 2)

    def test_inconsistent_author_house_rotation_rejected_and_old_binding_kept(self):
        good = self.store.bind('house_a', 1, sample_capture())
        for broken in (
            {**sample_capture(), 'houseAnchorWorldCFrame': frame(10, 0, 0)},
            {**sample_capture(), 'houseAnchorWorldCFrame': frame(12, 0, 0)},
            {**sample_capture(), 'houseAnchorLocalCFrame': frame(0, 0, 0)},
            {**sample_capture(), 'houseAnchorLocalCFrame': frame(0, 0, 0)[:11]},
            {**sample_capture(), 'schemaVersion': 1},
        ):
            with self.subTest(broken=broken), self.assertRaises(ValueError):
                self.store.bind('house_a', 1, broken)
        self.assertEqual(self.store.get('house_a', 1), good)

    def test_legacy_migration_does_not_reinterpret_cframe(self):
        captured = sample_capture()
        stored = self.store.bind('house_a', 1, captured)
        with sqlite3.connect(self.store.db) as connection:
            connection.execute('ALTER TABLE real_estate_placements RENAME TO old_rotations')
            connection.execute('''CREATE TABLE real_estate_placements (
                plot_index INTEGER NOT NULL, house_slug TEXT NOT NULL,
                plot_volume TEXT NOT NULL, world_cframe_json TEXT NOT NULL,
                plot_cframe_json TEXT NOT NULL, local_cframe_json TEXT NOT NULL,
                model_scale REAL NOT NULL, revision INTEGER NOT NULL,
                anchored INTEGER NOT NULL DEFAULT 1, updated_at REAL NOT NULL,
                PRIMARY KEY(plot_index,house_slug))''')
            connection.execute('''INSERT INTO real_estate_placements SELECT
                plot_index, house_slug, plot_volume, world_cframe_json, plot_cframe_json,
                local_cframe_json, model_scale, revision, anchored, updated_at
                FROM old_rotations''')
            connection.execute('DROP TABLE old_rotations')
        reopened = RealEstatePlacementStore(self.root, self.store.houses)
        old = reopened.get('house_a', 1)
        self.assertIsNone(old['houseAnchorLocalCFrame'])
        for key in ('worldCFrame', 'plotCFrame', 'localCFrame', 'scale', 'revision', 'anchored'):
            self.assertEqual(old[key], stored[key])
        self.assertEqual(len(list((self.store.db.parent/'backups').glob('before_placement_rotation_m229_*.db'))), 1)
        new = reopened.bind('house_a', 1, captured)
        self.assertEqual(new['houseAnchorLocalCFrame'], captured['houseAnchorLocalCFrame'])

    def test_studio_bridge_accepts_old_binding_without_rebind(self):
        legacy = {'anchored': True, 'revision': 1, 'scale': 1,
                  'houseSlug': 'house_a', 'plotIndex': 1,
                  'localCFrame': frame(), 'houseAnchorLocalCFrame': None}
        with mock.patch('services.studio_house_placement_bridge._request_house_placement') as request:
            request.return_value = {'status': 'placed', 'anchored': True,
                                    'anchoredPartsVerified': 1,
                                    'rotationMode': 'legacy-model-pivot'}
            result = preview_house_placement('house_a', 1, 'place', legacy)
            self.assertEqual(result['rotationMode'], 'legacy-model-pivot')
            self.assertIsNone(request.call_args.kwargs['placement']['houseAnchorLocalCFrame'])
            request.return_value = {'status': 'placed_all', 'changed': 1,
                                    'anchoredPartsVerified': 2, 'legacyPlacements': 1}
            result = bulk_house_placements('house_a', 'place_all', [legacy])
            self.assertEqual(result['legacyPlacements'], 1)
            self.assertEqual(request.call_args.kwargs['targets'], [legacy])

    def test_studio_bridge_still_rejects_corrupted_anchor(self):
        legacy = {'anchored': True, 'revision': 1, 'scale': 1,
                  'houseSlug': 'house_a', 'plotIndex': 1,
                  'localCFrame': frame(), 'houseAnchorLocalCFrame': frame()[:11]}
        with mock.patch('services.studio_house_placement_bridge._request_house_placement') as request:
            with self.assertRaisesRegex(ValueError, 'invalid saved house-anchor'):
                preview_house_placement('house_a', 1, 'place', legacy)
            with self.assertRaisesRegex(ValueError, 'invalid saved house-anchor'):
                bulk_house_placements('house_a', 'place_all', [legacy])
            request.assert_not_called()

    def test_shared_house_frame_and_versioned_studio_commands(self):
        plugin = ROOT/'system/studio-plugin/modules'
        capture = (plugin/'StudioHousePlacementCapture.luau').read_text()
        preview = (plugin/'StudioHousePlacementPreview.luau').read_text()
        bridge = (ROOT/'system/control-center/services/studio_house_placement_bridge.py').read_text()
        router = (ROOT/'system/studio-plugin/Game1Bridge.server.luau').read_text()
        self.assertIn('HouseFrame.Find(model)', capture)
        self.assertIn('world:ToObjectSpace(houseWorld)', capture)
        self.assertIn('houseAnchorLocalCFrame', capture)
        self.assertIn('HouseFrame.Find(clone)', preview)
        self.assertIn('HouseFrame.Align(clone, house, desiredHouse', preview)
        self.assertIn('local desiredHouse = desiredRoot * houseOffset', preview)
        self.assertNotIn('clone:PivotTo(volume.CFrame * CFrame.new(table.unpack(components)))', preview)
        self.assertIn('house-placement-capture-v2', bridge)
        self.assertIn('house-placement-preview-v4', bridge)
        self.assertIn('data.command == "house-placement-preview-v4"', router)
        self.assertIn('data.command == "house-placement-capture-v2"', router)
        self.assertIn('legacyPivot = binding.houseAnchorLocalCFrame == nil', preview)
        self.assertIn('clone:GetPivot():ToObjectSpace(house:GetPivot())', preview)
        self.assertIn('if legacyPivot then "legacy-model-pivot" else "house-anchor-v2"', preview)
