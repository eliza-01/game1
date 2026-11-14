"""M343B1: published visual identity + folder-free multi-selection contract."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from location_asset_store import LocationAssetStore
from services.location_collision_identity import expected_versions
from services.location_collision_authoring import LocationCollisionAuthoring
from services.studio_location_collision_bridge import run_location_collision_bridge


class CollisionMultiSelectM343B1(unittest.TestCase):
    def _store(self, path):
        store = LocationAssetStore(path)
        with store.connect() as db:
            db.executemany(
                'INSERT INTO location_assets(slug,name_en,category,model_asset_id,created_at,updated_at) '
                'VALUES(?,?,?,?,?,?)',
                [('stone_fence_01', 'Fence', 'fence', '555', 0, 0),
                 ('other_fence', 'Other', 'fence', '999', 0, 0)])
        return store

    def _inventory(self, store, slug, model_id, meshes):
        with store.connect() as db:
            db.execute('INSERT INTO location_asset_mesh_id_inventory '
                       '(asset_slug,model_asset_id,meshes_json,observed_at) VALUES(?,?,?,?)',
                       (slug, model_id, json.dumps(meshes), 1))

    def test_historical_visual_provenance_ignores_old_col_and_carrier(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(Path(tmp))
            self._inventory(store, 'stone_fence_01', '555', [
                {'meshId': '101', 'count': 2, 'visualNames': ['fence']},
                {'meshId': '202', 'count': 1, 'visualNames': []},
                {'meshId': '303', 'count': 1, 'visualNames': []},
            ])
            expected = expected_versions(store, 'stone_fence_01')
            self.assertEqual(expected, [
                {'modelAssetId': '555', 'meshes': [{'meshId': '101', 'count': 2}]}])
            calls = []
            service = LocationCollisionAuthoring(store, lambda **kw: calls.append(kw) or {'partCount': 0})
            service.operate('stone_fence_01', 'clear-preview')
            self.assertIsNone(calls[-1]['expected_versions'])
            self.assertEqual(calls[-1]['phase'], 'clear-preview')

    def test_name_or_stamp_cannot_authorize_ambiguous_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(Path(tmp))
            for slug, model_id in [('stone_fence_01', '555'), ('other_fence', '999')]:
                self._inventory(store, slug, model_id,
                                [{'meshId': '101', 'count': 1, 'visualNames': ['same']}])
            with self.assertRaisesRegex(ValueError, 'another Location Asset'):
                expected_versions(store, 'stone_fence_01')

    def test_missing_publication_or_inventory_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(Path(tmp))
            with self.assertRaisesRegex(ValueError, 'inventory'):
                expected_versions(store, 'stone_fence_01')
            with store.connect() as db:
                db.execute('UPDATE location_assets SET model_asset_id=NULL WHERE slug=?',
                           ('stone_fence_01',))
            with self.assertRaisesRegex(ValueError, 'published'):
                expected_versions(store, 'stone_fence_01')

    def test_transport_requires_published_signature_for_selected_model(self):
        with self.assertRaisesRegex(ValueError, 'inventory'):
            run_location_collision_bridge(slug='stone_fence_01', phase='capture',
                                          expected_revision=0)

    def test_studio_contract_no_authoring_folder_or_pivot_mutation(self):
        source = (ROOT / 'system/studio-plugin/modules/StudioLocationCollisionAuthoring.luau').read_text(encoding='utf-8')
        page = (ROOT / 'system/control-center/static/index.html').read_text(encoding='utf-8')
        self.assertIn('local picked = selection:Get()', source)
        self.assertIn('table.insert(parts, item)', source)
        self.assertIn('sameInventory(root, version)', source)
        self.assertIn('root:GetPivot()', source)
        self.assertIn('a:GetFullName()', source)
        self.assertIn('part.Name:gsub', source)
        self.assertNotIn('FindFirstChild(AUTHOR_FOLDER)', source)
        self.assertNotIn('root:PivotTo(', source)
        self.assertNotIn('root.WorldPivot =', source)
        self.assertNotIn('root.PrimaryPart =', source)
        self.assertNotIn('root:IsDescendantOf(container)', source)
        self.assertNotIn('if part.CanCollide then', source)
        self.assertIn('Preview', page)
        self.assertNotIn('создай прямую папку', page)
        self.assertIn('не нужно', page)


if __name__ == '__main__':
    unittest.main()
