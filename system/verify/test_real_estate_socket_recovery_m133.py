"""Publication owns all bones; Studio never reconstructs them."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from real_estate.studio_sync import RealEstateStudioSync

IDENTITY = [1., 0., 0., 0.,
            0., 1., 0., 0.,
            0., 0., 1., 0.,
            0., 0., 0., 1.]


class RestoredSocketsM133(unittest.TestCase):
    def test_sync_requests_imported_bones_without_reconstruction_metadata(self):
        hinge = {'name': 'door_01_hinge_socket', 'parent': '', 'matrixLocal': IDENTITY}
        child = {'name': 'door_01_handle_outside_socket',
                 'parent': hinge['name'], 'matrixLocal': [1,0,0,3, 0,1,0,4, 0,0,1,5, 0,0,0,1]}
        house = {'name': 'house', 'bones': [], 'armature': 'house_armature'}
        door = {'name': 'door', 'bones': [hinge, child], 'armature': 'door_armature'}
        row = {'slug': 'house_level4_01', 'status': 'PUBLISHED', 'skeleton': {'meshes': [house, door]},
               'rigAssets': {'house': {'assetId': '111'}, 'door': {'assetId': '222'}},
               'house_level': 4, 'purchase_price': 1, 'min_level': 1, 'sale_price': 1,
               'textures': {'house': {'assetId': '333'}, 'door': {'assetId': '444'}}}
        store = Mock()
        store.get.return_value = row
        store.root = ROOT
        load = Mock(return_value={'realEstateStats': {'bonesValidated': True,
                        'rigsValidated': 2, 'texturesApplied': 2}})
        RealEstateStudioSync(store, load).sync(row['slug'])
        metadata = load.call_args.kwargs['metadata']
        self.assertNotIn('authoredBones', metadata)
        self.assertEqual(metadata['expectedMeshes']['door'], [hinge['name'], child['name']])
        self.assertEqual(load.call_args.args[0], '111')
        self.assertEqual(load.call_args.kwargs['placement_mode'], 'real-estate-rig')

    def test_recovery_removed_from_sources_and_packaging(self):
        self.assertFalse((ROOT / 'system/studio-plugin/modules/StudioRealEstateSocketRecovery.luau').exists())
        for path in ('system/studio-plugin/modules/StudioRealEstateModel.luau',
                     'system/studio-plugin/modules/StudioRealEstatePartSync.luau',
                     'system/studio-plugin/plugin.project.json', 'system/studio-plugin/install.ps1'):
            self.assertNotIn('StudioRealEstateSocketRecovery', (ROOT / path).read_text())
        self.assertNotIn('recoveredSockets', (ROOT / 'system/control-center/static/real-estate.js').read_text())

    def test_no_changes_to_image_or_model_publication_pipeline(self):
        # Only Studio read-side recovery. No model/texture upload is part of
        # clicking Studio Sync. This is critical for published ID stability.
        script = (ROOT / 'system/control-center/real_estate/studio_sync.py').read_text()
        self.assertNotIn('create_model_asset', script)
        self.assertNotIn('create_image_asset', script)
        self.assertNotIn('ensure_published', script)
        self.assertNotIn('authoredBones', script)


if __name__ == '__main__':
    unittest.main()
