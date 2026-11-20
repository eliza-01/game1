"""Regression coverage for normalized historical Location rig comparison.

Roblox Studio execution is still required to exercise LoadAssetAsync and the
actual importer RootPart/Motor6D hierarchy.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
CONTROL = ROOT / 'system' / 'control-center'
if str(CONTROL) not in sys.path:
    sys.path.insert(0, str(CONTROL))

from location_asset_store import LocationAssetStore


class _HistoryStore:
    def model_publication_ids(self, slug):
        assert slug == 'smithy_01'
        return ['222', '111']

    def mesh_id_inventory(self, slug):
        assert slug == 'smithy_01'
        return [{'modelAssetId': '111', 'meshes': [{'meshId': '900', 'count': 1}]}]

    def rig_manifest(self, slug, model_id):
        assert slug == 'smithy_01'
        return {'schemaVersion': 2, 'structuralHash': 'hash-' + model_id}


class HistoricalRigComparisonTest(unittest.TestCase):
    def source(self, relative):
        return (ROOT / relative).read_text(encoding='utf-8')

    def test_history_pairs_each_model_with_its_own_manifest(self):
        rows = LocationAssetStore.model_history_inventory(_HistoryStore(), 'smithy_01')
        self.assertEqual([row['modelAssetId'] for row in rows], ['222', '111'])
        self.assertEqual(rows[0]['meshes'], [])
        self.assertEqual(rows[0]['rigManifest']['structuralHash'], 'hash-222')
        self.assertEqual(rows[1]['meshes'][0]['meshId'], '900')
        self.assertEqual(rows[1]['rigManifest']['structuralHash'], 'hash-111')

    def test_sync_uses_detached_historical_runtime_shape(self):
        loader = self.source('system/studio-plugin/modules/DecoAssetLoader.luau')
        scoped = self.source('system/studio-plugin/modules/DecoPlacedAssetSync.luau')
        registry = self.source('system/studio-plugin/modules/StudioPlaceRegistrySync.luau')
        history = self.source('system/studio-plugin/modules/StudioPublishedMeshHistory.luau')

        method = loader.split('function DecoAssetLoader:loadHistoricalRigForComparison', 1)[1]
        self.assertIn('self:loadForMeshInventory(modelId, slug)', method)
        self.assertIn('PublishedRigNormalize.Apply(model, rigManifest)', method)
        self.assertIn('Carrier.Validate(model, rigManifest, false)', method)
        self.assertIn('SkinConnection.Connect(model, carrier, part, "LocationSkinWeld")', method)
        self.assertIn('historical rig manifest unavailable; no Place geometry modified', method)
        self.assertIn('previousVersion.rigManifest', scoped)
        self.assertIn('version.rigManifest', registry)
        self.assertIn('loadHistoricalRigForComparison(', scoped)
        self.assertIn('loadHistoricalRigForComparison(', registry)
        # The raw immutable loader remains available for scan/forensics.
        self.assertIn('loader:loadForMeshInventory(modelId,slug)', history)

    def test_transport_keeps_manifest_when_studio_refreshes_mesh_cache(self):
        write_world = self.source('system/control-center/api/write_world.py')
        catalog = self.source('system/control-center/services/place_registry/catalog.py')
        scan = self.source('system/studio-plugin/modules/StudioPublishedMeshHistory.luau')
        registry = self.source('system/studio-plugin/modules/StudioPlaceRegistryInventory.luau')
        self.assertIn("location_assets.model_history_inventory(slug)", write_world)
        self.assertIn("hasattr(location_assets, 'model_history_inventory')", write_world)
        self.assertIn("'rigManifest': inventory.get(identifier, {}).get('rigManifest')", catalog)
        self.assertIn('desc.rigManifest=cache[modelId].rigManifest', scan)
        self.assertIn('info.rigManifest=version.rigManifest', registry)

    def test_arbitrary_part_guard_is_not_weakened(self):
        history = self.source('system/studio-plugin/modules/StudioPublishedMeshHistory.luau')
        verify = history.split('function Inventory.VerifyChildren(', 1)[1].split('function Inventory.Scan(', 1)[0]
        self.assertIn('actualOtherParts[className] ~= count', verify)
        self.assertIn('unverified extra physical part in managed geometry', verify)
        self.assertIn('unverified placed rig descendant', verify)


if __name__ == '__main__':
    unittest.main()
