"""M133: true socket Bone restoration in Studio without deforming published meshes.

Roblox physics/CFrame still requires a manual Studio test: these unit tests
assert that authoring transforms reach the Bridge and no mutation/publication
is introduced by the Studio-only recovery path.
"""
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
    def test_authoritative_rest_matrices_transmitted_unmodified(self):
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
                        'rigsValidated': 2, 'texturesApplied': 2, 'recoveredSockets': ['door/door_01_handle_outside_socket']}})
        RealEstateStudioSync(store, load).sync(row['slug'])
        metadata = load.call_args.kwargs['metadata']
        self.assertEqual(metadata['authoredBones']['door'], [hinge, child])
        self.assertEqual(metadata['authoredBones']['house'], [])
        self.assertEqual(load.call_args.args[0], '111')
        self.assertEqual(load.call_args.kwargs['placement_mode'], 'real-estate-rig')

    def test_restorer_uses_imported_parents_and_authored_relative_transforms(self):
        script = (ROOT / 'system/studio-plugin/modules/StudioRealEstateSocketRecovery.luau').read_text()
        assembly = (ROOT / 'system/studio-plugin/modules/StudioRealEstateModel.luau').read_text()
        validation = (ROOT / 'system/studio-plugin/modules/StudioRealEstateRigValidation.luau').read_text()
        self.assertIn('specs[spec.parent].frame:ToObjectSpace(spec.frame)', script)
        self.assertIn('replacement.CFrame = localFrame', script)
        self.assertIn('replacement.Parent = parent', script)
        self.assertIn('Instance.new("Bone")', script)
        self.assertIn('instance:IsA("Attachment")', script)
        self.assertIn('parent:IsA("Bone")', script)
        self.assertIn('Game1RecoveredFromFBXRestPose', script)
        self.assertIn('imported parent bone unavailable; cannot restore exactly', script)
        self.assertNotIn('Transform =', script)
        self.assertNotIn('Instance.new("MeshPart")', script)
        self.assertIn('StudioRealEstateSocketRecovery.Restore(candidate, authored)', assembly)
        self.assertLess(assembly.index('StudioRealEstateSocketRecovery.Restore('),
                        assembly.index('StudioRealEstateRigValidation.Verify('))
        self.assertIn('Game1RecoveredRealEstateSockets', assembly)
        self.assertIn('function Validation.FindMesh(', validation)
        self.assertIn('StudioRealEstateRigValidation.FindMesh(rig, part)', assembly)
        self.assertIn('assembly.WorldPivot = hinge.TransformedWorldCFrame', assembly)
        self.assertNotIn('hinge.Transform =', assembly)

    def test_plugin_and_frontend_consume_recovery_stats(self):
        tree = json.loads((ROOT / 'system/studio-plugin/plugin.project.json').read_text())
        self.assertEqual(tree['tree']['modules']['StudioRealEstateSocketRecovery']['$path'],
                         'modules/StudioRealEstateSocketRecovery.luau')
        self.assertIn("'StudioRealEstateSocketRecovery',",
                      (ROOT / 'system/studio-plugin/install.ps1').read_text())
        ui = (ROOT / 'system/control-center/static/real-estate.js').read_text()
        self.assertIn('const recovered=stats.recoveredSockets||[];', ui)
        self.assertIn('sockets recovered', ui)

    def test_no_changes_to_image_or_model_publication_pipeline(self):
        # Only Studio read-side recovery. No model/texture upload is part of
        # clicking Studio Sync. This is critical for published ID stability.
        script = (ROOT / 'system/control-center/real_estate/studio_sync.py').read_text()
        self.assertNotIn('create_model_asset', script)
        self.assertNotIn('create_image_asset', script)
        self.assertNotIn('ensure_published', script)
        self.assertIn('authoredBones', script)


if __name__ == '__main__':
    unittest.main()
