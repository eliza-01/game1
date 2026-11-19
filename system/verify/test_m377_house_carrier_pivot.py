"""M377: a house has exactly one technical root and independent Plot data."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system' / 'control-center'))
from real_estate.rig_publication_policy import (publication_analysis, primary_part,
        publish_bones_for_mesh, publication_fingerprint)
from real_estate.placement import RealEstatePlacementStore


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


class CanonicalHouseRigTest(unittest.TestCase):
    def sample(self):
        bones = [{'name': 'houseplant_01', 'parent': ''},
                 {'name': 'door_01_hinge_socket', 'parent': ''},
                 {'name': 'door_01_handle_inside_socket', 'parent': 'door_01_hinge_socket'}]
        return {'houseArmatureBones': bones, 'meshes': [
            {'name': 'chimney', 'armature': '', 'bones': [], 'influencedBones': []},
            {'name': 'roof', 'armature': '', 'bones': [], 'influencedBones': []},
            {'name': 'door', 'armature': 'house_armature', 'bones': bones,
             'influencedBones': ['door_01_hinge_socket']} ]}

    def test_visual_part_never_owns_socket_skeleton(self):
        analysis = publication_analysis(self.sample())
        self.assertEqual(primary_part(analysis), 'chimney')
        entry = next(m for m in analysis['meshes'] if m['name'] == 'chimney')
        self.assertFalse(entry['socketCarrier'])
        self.assertEqual(publish_bones_for_mesh(entry), [])
        self.assertFalse(entry['generatedCarrierRig'])
        self.assertEqual([b['name'] for b in analysis['carrierBones']], ['houseplant_01'])
        self.assertEqual([b['name'] for b in publish_bones_for_mesh(
            next(m for m in analysis['meshes'] if m['name'] == 'roof'))], [])

    def test_unweighted_mesh_only_and_original_armature_required(self):
        manifest = self.sample()
        manifest['meshes'] = manifest['meshes'][1:2]
        self.assertEqual(primary_part(manifest), 'roof')
        self.assertEqual(publication_analysis(manifest)['primaryPart'], 'rig_carrier')
        manifest['houseArmatureBones'] = []
        with self.assertRaisesRegex(ValueError, 'house_armature'):
            publication_analysis(manifest)
        manifest['meshes'][0]['influencedBones'] = ['houseplant_01']
        self.assertEqual(primary_part(manifest), 'roof')

    def test_fbx_staging_reuses_character_location_carrier_mechanism(self):
        staging = read('system/asset-manager/prepare_real_estate_publication_fbx.py')
        self.assertIn('from blender_rig_carrier import create_rig_carrier', staging)
        self.assertIn('carrier = create_rig_carrier(house_rig)', staging)
        self.assertIn('source_to_house = house_rig.matrix_world.inverted() @ authored_world', staging)
        self.assertIn('mesh.data.transform(source_to_house)', staging)
        self.assertIn("export_model(output / 'rig_carrier.fbx', [carrier, rig]", staging)
        self.assertNotIn('[mesh, carrier, rig]', staging)
        self.assertIn('bpy.data.objects.remove(carrier, do_unlink=True)', staging)

    def test_blender_fbx_roundtrip_counts_technical_and_visual_separately(self):
        analysis = read('system/asset-manager/analyze_real_estate_fbx.py')
        contract = read('system/control-center/real_estate/contracts.py')
        self.assertIn("obj.name != 'rig_carrier'", analysis)
        self.assertIn('meshes.append(describe_mesh(bpy, carrier', analysis)
        self.assertIn("visuals = [row for row in staged if row['name'] != 'rig_carrier']", contract)
        self.assertIn('independent socket publication must contain only rig_carrier', contract)
        self.assertIn('visual publication must not contain rig_carrier', contract)

    def test_studio_root_is_not_a_visual_mesh_or_bounding_box(self):
        studio = read('system/studio-plugin/modules/StudioRealEstateModel.luau')
        placement = read('system/studio-plugin/modules/StudioRealEstatePartPlacement.luau')
        self.assertIn('rootCarrier, carrierInspection = StudioRealEstateRigValidation.Verify(', studio)
        self.assertIn('authoredOrigin = rootCarrier:GetPivot()', studio)
        self.assertIn('wrapper.PrimaryPart = rootCarrier', studio)
        self.assertIn('StaticAssembly', studio)
        self.assertIn('SkinConnection.Connect(static, rootCarrier', studio)
        self.assertNotIn('authoredOrigin = mesh:GetPivot()', studio)
        self.assertNotIn('PartPlacement.AlignOrigin(', studio)
        self.assertIn('rig:PivotTo(pivot)', placement)
        sync = read('system/control-center/real_estate/studio_sync.py')
        self.assertIn("'houseAuthoringVersion': 4", sync)
        self.assertIn("'syncPart': '',", sync)

    def test_publication_revision_invalidates_older_unchanged_uploads(self):
        source_hash = 'e' * 64
        carrier = publication_fingerprint(source_hash, carrier=True)
        static = publication_fingerprint(source_hash, carrier=False)
        self.assertEqual(len(carrier), 64)
        self.assertNotEqual(carrier, source_hash)
        self.assertNotEqual(static, source_hash)
        self.assertNotEqual(carrier, static)
        self.assertEqual(carrier, publication_fingerprint(source_hash, carrier=True))
        store = read('system/control-center/real_estate/store.py')
        self.assertIn("row['rigPublicationHashes']", store)
        self.assertIn("row['rigPublicationHashes'][part]", store)
        studio = read('system/control-center/real_estate/studio_sync.py')
        self.assertIn('Republish independent rig_carrier', studio)

    def test_plot_identity_preserved_without_house_record(self):
        class Registry:
            def get(self, _):
                return None
        cf = [12, 0, 36, 1,0,0, 0,1,0, 0,0,1]
        identity = [0,0,0, 1,0,0, 0,1,0, 0,0,1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.control-center').mkdir()
            store = RealEstatePlacementStore(root, Registry())
            binding = store.bind('house_level5_01', 39, {
                'schemaVersion': 2, 'houseSlug': 'house_level5_01', 'plotIndex':39,
                'plotVolume':'plot_39_volume', 'worldCFrame':cf, 'plotCFrame':cf,
                'localCFrame':identity, 'houseAnchorLocalCFrame':identity,
                'houseAnchorWorldCFrame':cf, 'scale':1.5,
            })
            self.assertEqual(RealEstatePlacementStore(root, Registry()).get('house_level5_01',39), binding)

if __name__ == '__main__':
    unittest.main()
