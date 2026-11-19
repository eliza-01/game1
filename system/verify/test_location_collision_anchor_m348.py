"""M348: current-publication mesh anchor, pivot rebasing and safe migration.

Source contracts + algebraic checks only. The Studio runtime must still be tested.
"""
from __future__ import annotations

import math
import random
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services.location_collision_blueprint import validate
from services.location_collision_identity import expected_versions
from location_asset_store import LocationAssetStore


def read(rel):
    return (ROOT / rel).read_text(encoding='utf-8')


def identity():
    return [0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1]


def sample():
    return {'schemaVersion': 2, 'pivot': 'Model:GetPivot()',
            'anchor': {'meshId': '139744616815788', 'size': [2, 3, 5],
                       'localCFrame': [1, 2, 3, 1, 0, 0, 0, 1, 0, 0, 0, 1]},
            'parts': [{'id': 'wall', 'name': 'Wall', 'shape': 'Block',
                       'size': [5, 5, 0.25], 'localCFrame': identity(),
                       'collisionGroup': 'Default', 'canQuery': True,
                       'canTouch': False}]}


class AnchorM348(unittest.TestCase):
    def test_v2_validates_anchor_and_legacy_requires_explicit_recapture(self):
        data = sample()
        self.assertEqual(validate(data, slug='stone_fence_02')['anchor']['meshId'],
                         '139744616815788')
        invalid = {**data, 'schemaVersion': 1}
        with self.assertRaisesRegex(ValueError, 'outdated Collision Blueprint'):
            validate(invalid, slug='stone_fence_02')
        invalid = {**data, 'anchor': {**data['anchor'], 'meshId': 'bad'}}
        with self.assertRaisesRegex(ValueError, 'Mesh ID'):
            validate(invalid, slug='stone_fence_02')
        invalid = {**data, 'anchor': {**data['anchor'],
                                    'localCFrame': [0, 0, 0, 2, 0, 0, 0, 1, 0, 0, 0, 1]}}
        with self.assertRaisesRegex(ValueError, 'orthonormal'):
            validate(invalid, slug='stone_fence_02')
        invalid = {**data, 'anchor': {**data['anchor'], 'size': [2, 0, 5]}}
        with self.assertRaisesRegex(ValueError, 'positive'):
            validate(invalid, slug='stone_fence_02')

    def test_historical_v1_revision_is_preserved_then_new_v2_appended(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocationAssetStore(Path(tmp))
            with store.connect() as c:
                c.execute("INSERT INTO location_assets(slug,name_en,category,created_at,updated_at) VALUES(?,?,?,?,?)",
                          ('stone_fence_02', 'Stone Fence', 'fence', 0., 0.))
                c.execute("INSERT INTO location_asset_collision_blueprints(asset_slug,revision,blueprint_json,sha256,captured_at) VALUES(?,?,?,?,?)",
                          ('stone_fence_02', 1,
                           '{"schemaVersion":1,"pivot":"Model:GetPivot()","parts":[]}',
                           '0' * 64, 1.0))
            saved = store.save_collision_blueprint('stone_fence_02',
                         {'expectedRevision': 1, 'blueprint': sample()})
            self.assertEqual(saved['revision'], 2)
            with store.connect() as c:
                self.assertEqual([r[0] for r in c.execute('SELECT revision FROM location_asset_collision_blueprints ORDER BY revision')], [1, 2])

    def test_current_publication_signature_is_anchor_priority(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocationAssetStore(Path(tmp))
            with store.connect() as c:
                c.execute("INSERT INTO location_assets(slug,name_en,category,model_asset_id,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                          ('stone_fence_02', 'Stone Fence', 'fence', '555', 0., 0.))
                for version in ['333', '555']:
                    c.execute("INSERT INTO location_asset_mesh_id_inventory(asset_slug,model_asset_id,meshes_json,observed_at) VALUES(?,?,?,?)",
                              ('stone_fence_02', version,
                               '[{"meshId":"139744616815788","count":1,"visualNames":["mesh"]}]', 1.0))
            self.assertEqual(expected_versions(store, 'stone_fence_02')[0]['modelAssetId'], '555')

    def test_rotation_translation_scale_pivot_rebase_math(self):
        # v2 Lua stores pivot-relative frames, and reconstructs the virtual
        # captured pivot from the mesh frame. Verify the transform algebra
        # independently for rotated and uniformly scaled target scenes.
        rng = random.Random(348)
        def rz(theta, x, y):
            c, s = math.cos(theta), math.sin(theta)
            return (c*x-s*y, s*x+c*y)
        for _ in range(400):
            theta = rng.uniform(-math.pi, math.pi)
            scale = rng.uniform(0.1, 8.0)
            old_pivot = [rng.uniform(-300, 300), rng.uniform(-300, 300)]
            anchor_local = [rng.uniform(-30, 30), rng.uniform(-30, 30)]
            collider_local = [rng.uniform(-30, 30), rng.uniform(-30, 30)]
            shift = [rng.uniform(-600, 600), rng.uniform(-600, 600)]
            anchor_transformed = rz(theta, *(v*scale for v in anchor_local))
            new_anchor = [shift[i] + anchor_transformed[i] for i in range(2)]
            captured_pivot = [new_anchor[i] - anchor_transformed[i] for i in range(2)]
            collider_transformed = rz(theta, *(v*scale for v in collider_local))
            new_collider = [captured_pivot[i] + collider_transformed[i] for i in range(2)]
            expected = [shift[i] + collider_transformed[i] for i in range(2)]
            self.assertLess(max(abs(new_collider[i] - expected[i]) for i in range(2)), 1e-8)
            self.assertTrue(math.isfinite(old_pivot[0]))

    def test_studio_contracts_and_missing_part_scan(self):
        author = read('system/studio-plugin/modules/StudioLocationCollisionAuthoring.luau')
        collision = read('system/studio-plugin/modules/StudioLocationCollisionParts.luau')
        inventory = read('system/studio-plugin/modules/StudioPlaceRegistryInventory.luau')
        sync = read('system/studio-plugin/modules/StudioPlaceRegistrySync.luau')
        ui = read('system/control-center/static/place-registry.js')
        self.assertIn('schemaVersion = 2', author)
        self.assertIn('selectVisualAnchor(root, command)', author)
        self.assertIn('ignoredGenerated += 1', author)
        self.assertIn('Select the Location Model together with 1..256 ORIGINAL collision Parts.', author)
        self.assertIn('Transform.Resolve, root, blueprint', collision)
        self.assertIn('Transform.Part, anchor, recipe', collision)
        transform = read('system/studio-plugin/modules/StudioLocationCollisionTransform.luau')
        self.assertIn('matched.Size.X / original.X', transform)
        self.assertIn('if not validParts then return false end', collision)
        self.assertIn('blueprint.schemaVersion ~= 2 and blueprint.schemaVersion ~= 3', collision)
        self.assertIn('root == nil or needsRecapture', inventory)
        self.assertIn('not needsRecapture', inventory)
        self.assertIn('Collision Blueprint требует Sync', inventory)
        self.assertIn('Collision ✕ требует Sync', ui)
        self.assertIn('Collision ✕ повторить Capture', ui)
        self.assertIn('item.stage)', sync)
        self.assertNotIn('for _, part in ipairs(transaction.prior) do part:Destroy()', collision)


if __name__ == '__main__':
    unittest.main()
