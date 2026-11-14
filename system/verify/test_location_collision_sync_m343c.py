"""M343C: real SQLite registry propagation + Studio Place/Sync source contracts.

Roblox runtime physics is verified manually in Studio; this suite does not
pretend static Luau checks are an in-engine simulation.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from location_asset_store import LocationAssetStore
from services.place_registry.catalog import build_catalog, validate_report

BLUEPRINT = {'schemaVersion': 1, 'pivot': 'Model:GetPivot()', 'parts': [
    {'id': 'wall', 'name': 'wall', 'shape': 'Block', 'size': [4, 3, 1],
     'localCFrame': [0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1],
     'collisionGroup': 'Default', 'canQuery': False, 'canTouch': False},
]}


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


class CollisionSyncM343C(unittest.TestCase):
    def test_catalog_revisions_data_and_digest_follow_capture(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fbx = root / 'untouched.fbx'
            fbx.write_bytes(b'FBX fixture: publication is only simulated via SQL')
            store = LocationAssetStore(root)
            store.register({'nameEn': 'Stone Fence', 'slug': 'stone_fence_02',
                            'category': 'fence', 'modelSourcePath': str(fbx),
                            'appearanceMode': 'material', 'visualMaterial': 'Slate',
                            'visualColor': '#7C7C7C', 'surfaceMaterial': 'stone',
                            'destructible': False})
            with store.connect() as db:
                db.execute('UPDATE location_assets SET model_asset_id=?, '
                           'model_published_sha256=model_sha256 WHERE slug=?',
                           ('84002732967561', 'stone_fence_02'))
            empty = build_catalog(store)
            self.assertEqual(len(empty['items']), 1)
            self.assertEqual(empty['items'][0]['collisionBlueprintRevision'], 0)
            saved = store.save_collision_blueprint('stone_fence_02',
                {'expectedRevision': 0, 'blueprint': BLUEPRINT})
            row = store.get('stone_fence_02')
            self.assertEqual(row['collisionBlueprintRevision'], 1)
            self.assertEqual(row['collisionBlueprintSha256'], saved['sha256'])
            self.assertEqual(row['collisionBlueprint'], saved['blueprint'])
            latest = build_catalog(store)
            self.assertEqual(latest['items'][0]['collisionBlueprint'], saved['blueprint'])
            self.assertEqual(latest['items'][0]['collisionBlueprintSha256'], saved['sha256'])
            self.assertNotEqual(latest['digest'], empty['digest'])
            changed = {**BLUEPRINT, 'parts': [{**BLUEPRINT['parts'][0], 'size': [6, 3, 1]}]}
            second = store.save_collision_blueprint('stone_fence_02',
                {'expectedRevision': 1, 'blueprint': changed})
            self.assertEqual(build_catalog(store)['items'][0]['collisionBlueprintRevision'], 2)
            self.assertNotEqual(second['sha256'], saved['sha256'])
            self.assertEqual(store.get('stone_fence_02')['visualMaterial'], 'Slate')

    def test_place_pipeline_always_fetches_fresh_blueprint(self):
        manager = source('system/studio-plugin/modules/DecoManager.luau')
        placement = source('system/studio-plugin/modules/DecoPlacement.luau')
        self.assertIn('pcall(self.loader.fetchRegistry, self.loader)', manager)
        self.assertIn('self.placement:start(self.template, chosen', manager)
        self.assertIn('row.collisionBlueprintRevision', placement)
        self.assertIn('pcall(Collision.Prepare, placed, row.collisionBlueprint', placement)
        self.assertIn('pcall(Collision.Commit, transaction)', placement)
        self.assertIn('Collision.Rollback(transaction)', placement)

    def test_generated_parts_only_and_pivot_preserved(self):
        module = source('system/studio-plugin/modules/StudioLocationCollisionParts.luau')
        self.assertIn('Game1LocationCollisionOwned', module)
        self.assertIn('part:IsA("MeshPart")', module)
        self.assertIn('root:GetPivot()', module)
        self.assertNotIn('PivotTo(', module)
        self.assertNotIn('PivotOffset =', module)
        self.assertIn('part.Anchored = true', module)
        self.assertIn('part.CanCollide = true', module)
        self.assertIn('part.Transparency = 1', module)
        self.assertIn('Collision.Finalize', module)
        self.assertIn('Collision.Rollback', module)
        self.assertIn('root:GetScale()', module)
        self.assertIn('part.CanQuery = true', module)
        self.assertIn('for _, part in ipairs(transaction.prior)', module)
        plugin = source('system/studio-plugin/plugin.project.json')
        self.assertIn('StudioLocationCollisionParts.luau', plugin)
        self.assertIn('StudioPlotsVisibility', plugin)
        self.assertIn('StudioPlaceRegistryInventory', plugin)

    def test_place_registry_detects_and_repairs_collision_without_new_model(self):
        inventory = source('system/studio-plugin/modules/StudioPlaceRegistryInventory.luau')
        sync = source('system/studio-plugin/modules/StudioPlaceRegistrySync.luau')
        ui = source('system/control-center/static/place-registry.js')
        self.assertIn('Collision.Current(root,entry.collisionBlueprint', inventory)
        self.assertIn('needsCollision=needsCollision', inventory)
        self.assertIn('Collision Blueprint требует Sync', inventory)
        self.assertIn('Collision.Prepare, ref.root,', sync)
        self.assertIn('if item.collision then Collision.Commit(item.collision) end', sync)
        self.assertIn('if item.collision then Collision.Rollback(item.collision) end', sync)
        self.assertIn('if item.collision then Collision.Finalize(item.collision) end', sync)
        self.assertIn('if Collision.IsOwned(child) then continue end', sync)
        self.assertIn('needsCollision', ui)
        self.assertIn('Collision ✕ требует Sync', ui)
        self.assertIn('outdatedCollision', ui)
        self.assertIn("'outdatedCollision'", source('system/control-center/services/place_registry/coordinator.py'))
        self.assertIn('Collision.IsOwned(child)', source('system/studio-plugin/modules/DecoPlacedAssetSync.luau'))

    def test_registry_schema_validates_collision_boolean(self):
        catalog = {'items': [{'slug': 'stone_fence_02'}]}
        row = {'slug': 'stone_fence_02', 'key': 'p1', 'name': 'fence', 'path': 'Workspace.fence',
               'meshId': '133', 'textureId': '', 'placementId': '123', 'status': 'pending',
               'needsMesh': False, 'needsTexture': False, 'needsStructure': False,
               'duplicateId': False, 'ambiguous': False, 'hasModel': True, 'canSync': True,
               'needsCollision': True, 'issues': [], 'transform': {}}
        self.assertEqual(validate_report({'schemaVersion': 1, 'placements': [row]}, catalog)[0], row)
        with self.assertRaisesRegex(ValueError, 'needsCollision'):
            validate_report({'schemaVersion': 1, 'placements': [{**row, 'needsCollision': 'yes'}]}, catalog)


if __name__ == '__main__':
    unittest.main()
