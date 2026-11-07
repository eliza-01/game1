"""M254: Location Studio Sync is actionable independently of aggregate authoring status."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from unittest import TestCase, mock
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))

from api.write_world import route


class _Assets:
    def __init__(self, row):
        self.row = row
        self.atlases = mock.Mock(binding=lambda *_: {'revision': 4})

    def get(self, slug):
        return dict(self.row, slug=slug)

    def model_publication_ids(self, _slug):
        return [str(self.row.get('model_asset_id') or '')]

    def mesh_id_inventory(self, _slug):
        return []

    def record_mesh_id_inventory(self, _slug, _inventory):
        return None


class LocationSyncActionAvailableM254(TestCase):
    def test_update_available_asset_can_find_placed_models(self):
        assets = _Assets({'status': 'UPDATE_AVAILABLE', 'bindingRevision': 4,
                          'model_asset_id': '12345', 'texture_asset_id': '67890'})
        transport = mock.Mock(return_value={
            'inventory': [{'modelAssetId': '12345', 'meshes': []}],
            'parts': [], 'scanToken': 'a' * 32,
        })
        deps = defaultdict(lambda: None, {
            'location_assets': assets,
            'sync_location_assets_to_studio': transport,
            'location_asset_sync_history': mock.Mock(),
        })

        status, result = route('/api/location-assets/studio-sync',
            lambda: {'slug': 'new_model', 'phase': 'scan'}, deps)

        self.assertEqual(status, 200, result)
        transport.assert_called_once()

    def test_missing_publication_reports_resource_instead_of_status(self):
        assets = _Assets({'status': 'LOCAL_ONLY', 'bindingRevision': 4,
                          'model_asset_id': '', 'texture_asset_id': '67890'})
        deps = defaultdict(lambda: None, {'location_assets': assets})

        status, result = route('/api/location-assets/studio-sync',
            lambda: {'slug': 'new_model', 'phase': 'scan'}, deps)

        self.assertEqual(status, 400)
        self.assertEqual(result['error'], 'publish the Location Asset Model before Studio Sync')

    def test_library_and_workflow_do_not_disable_sync_by_status(self):
        library = (ROOT / 'system/control-center/static/deco-assets.js').read_text('utf-8')
        workflow = (ROOT / 'system/control-center/static/location-asset-workflow.js').read_text('utf-8')

        self.assertNotIn("row.status !== 'PUBLISHED'", library)
        self.assertNotIn("item.status!=='PUBLISHED'", workflow)
        self.assertIn("button('scan','Find Mesh IDs", workflow)


if __name__ == '__main__':
    import unittest
    unittest.main()
