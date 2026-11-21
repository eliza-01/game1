"""M408: a missing current-Model Mesh inventory must never cause a false stale-Mesh loop.

The exact lantern_01 failure had a current Model publication whose SQLite
mesh ID cache was [], despite Studio having already applied the current Mesh ID.
The Roblox asset reload itself still requires an Edit-mode Studio smoke test.
"""
from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from api.write_world import route
from location_asset_store import LocationAssetStore
from services.location_studio_sync_verification import classify_scan


class _Assets:
    def __init__(self):
        self.model_id = '118279766326390'
        self.recorded = []
        self.atlases = mock.Mock()

    def get(self, slug):
        assert slug == 'lantern_01'
        return {'slug': slug, 'status': 'PUBLISHED', 'model_asset_id': self.model_id,
                'texture_asset_id': '', 'appearanceMode': 'material',
                'bindingRevision': 16, 'revision': 16}

    def model_publication_ids(self, slug):
        return [self.model_id]

    def model_history_inventory(self, slug):
        return [{'modelAssetId': self.model_id, 'meshes': [], 'rigManifest': {}}]

    def record_mesh_id_inventory(self, slug, records):
        self.recorded.append(records)


class CurrentInventoryM408(TestCase):
    def test_current_empty_cache_is_reloaded_not_used_as_authority(self):
        scanner = (ROOT / 'system/studio-plugin/modules/StudioPublishedMeshHistory.luau').read_text('utf-8')
        scan = scanner.split('function Inventory.Scan(', 1)[1]
        reload_source = scan.split('local desc=cache[modelId]', 1)[1].split('table.insert(inventory,desc)', 1)[0]
        self.assertIn('modelId==newModelId and (#desc.meshes==0', reload_source)
        self.assertIn('loader:loadForMeshInventory(modelId,slug)', reload_source)
        self.assertIn('desc=Inventory.Describe(modelId,published)', reload_source)
        self.assertIn('published:Destroy()', reload_source)
        self.assertIn('if modelId==newModelId and #desc.meshes==0 then', reload_source)
        self.assertIn('if cache[modelId] then desc.rigManifest=cache[modelId].rigManifest end', reload_source)
        # Never infer the new MeshId from an old Place MeshPart or Blender name.
        self.assertNotIn('part.MeshId', reload_source)
        self.assertLess(reload_source.index('desc=Inventory.Describe'),
                        reload_source.index('if modelId==newModelId and #desc.meshes==0'))

    def test_real_sqlite_empty_cache_can_be_repaired_without_changing_publication(self):
        with TemporaryDirectory() as directory:
            store = LocationAssetStore(Path(directory))
            model_id = '118279766326390'
            store.record_mesh_id_inventory('lantern_01', [
                {'modelAssetId': model_id, 'meshes': []}])
            self.assertEqual(store.mesh_id_inventory('lantern_01')[0]['meshes'], [])
            published = [{'meshId': '82462379123855', 'count': 1,
                          'visualNames': ['lantern_01']},
                         {'meshId': '100737631851020', 'count': 1,
                          'visualNames': []}]
            store.record_mesh_id_inventory('lantern_01', [
                {'modelAssetId': model_id, 'meshes': published}])
            self.assertEqual(store.mesh_id_inventory('lantern_01'), [
                {'modelAssetId': model_id, 'meshes': published}])

    def test_api_rejects_empty_current_inventory_without_falsely_acknowledging(self):
        assets = _Assets()
        fake_scan = {'inventory': [{'modelAssetId': assets.model_id, 'meshes': []}],
                     'parts': [], 'scanToken': 'a'*32}
        deps = defaultdict(lambda: None, {
            'location_assets': assets,
            'sync_location_assets_to_studio': mock.Mock(return_value=fake_scan),
        })
        status, result = route('/api/location-assets/studio-sync',
            lambda: {'slug': 'lantern_01', 'phase': 'scan'}, deps)
        self.assertEqual(status, 400, result)
        self.assertIn('did not verify Mesh IDs', result['error'])
        self.assertEqual(assets.recorded, [])

    def test_verified_scan_replaces_empty_cache_and_reports_current_mesh(self):
        assets = _Assets()
        mesh = '82462379123855'
        fake_scan = {'inventory': [{'modelAssetId': assets.model_id,
                      'meshes': [{'meshId': mesh, 'count': 1, 'visualNames': ['lantern_01']}]}],
                     'parts': [{'key': 'p1', 'managed': True, 'meshCurrent': True,
                         'textureCurrent': True, 'alphaCurrent': True, 'physicsCurrent': True,
                         'needsMesh': False, 'needsTexture': False, 'needsAlpha': False,
                         'needsPhysics': False, 'republishRequired': False,
                         'needsFbxInspection': False, 'needsCanonicalReplacement': False}],
                     'scanToken': 'a'*32,
                     'mode': 'current', 'unmanagedMeshParts': 0,
                     'meshPending': 0, 'texturePending': 0, 'alphaPending': 0,
                     'physicsPending': 0, 'geometryPending': 0}
        self.assertEqual(classify_scan(fake_scan), 'current')
        deps = defaultdict(lambda: None, {
            'location_assets': assets,
            'sync_location_assets_to_studio': mock.Mock(return_value=fake_scan),
        })
        status, result = route('/api/location-assets/studio-sync',
            lambda: {'slug': 'lantern_01', 'phase': 'scan'}, deps)
        self.assertEqual(status, 200, result)
        self.assertEqual(assets.recorded[0][0]['meshes'][0]['meshId'], mesh)
        self.assertEqual(result['studio']['verification'], 'current')


if __name__ == '__main__':
    import unittest
    unittest.main()
