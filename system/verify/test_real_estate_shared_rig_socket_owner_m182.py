"""M182: shared house armature sockets belong to house, not its static submeshes."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from real_estate.rig_publication_policy import publish_bones_for_mesh
from real_estate.contracts import assert_rig_survived


def mesh(name, rig, bones, influences=()):
    return {'name': name, 'armature': rig,
            'bones': [{'name': bone, 'parent': '', 'matrixLocal': [1] * 16}
                      for bone in bones],
            'influencedBones': list(influences)}


class SharedRigSocketOwnership(unittest.TestCase):
    def test_static_shared_parts_do_not_own_house_sockets(self):
        source = mesh('structures_01', 'house_armature', ['land_spawn_01_socket', 'chest_01_socket'])
        self.assertEqual(publish_bones_for_mesh(source), [])
        self.assertEqual(len(source['bones']), 2, 'authoring manifest remains unchanged')

    def test_house_owner_door_and_skinned_part_retain_every_bone(self):
        bones = ['land_spawn_01_socket', 'chest_01_socket']
        for entry in [mesh('house', 'house_armature', bones),
                      mesh('door', 'door_armature', ['door_01_hinge_socket']),
                      mesh('moving_part', 'house_armature', bones, ['chest_01_socket']),
                      mesh('separate_sockets', 'socket_armature', bones)]:
            with self.subTest(part=entry['name']):
                self.assertEqual(len(publish_bones_for_mesh(entry)), len(entry['bones']))

    def test_staged_static_mesh_is_accepted_without_copied_bones(self):
        source = mesh('structures_01', 'house_armature', ['land_spawn_01_socket'])
        actual = mesh('structures_01', '', [])
        assert_rig_survived({'meshes': [source]}, {'meshes': [actual]}, 'structures_01')

    def test_staged_static_mesh_rejects_unexpected_shared_bones(self):
        source = mesh('structures_01', 'house_armature', ['land_spawn_01_socket'])
        with self.assertRaisesRegex(ValueError, 'changed bone names'):
            assert_rig_survived({'meshes': [source]}, {'meshes': [source]}, 'structures_01')

    def test_house_and_real_skinned_mesh_still_reject_missing_bones(self):
        for source in [mesh('house', 'house_armature', ['land_spawn_01_socket']),
                       mesh('structures_01', 'house_armature', ['land_spawn_01_socket'], ['land_spawn_01_socket'])]:
            with self.subTest(part=source['name']):
                with self.assertRaisesRegex(ValueError, 'changed bone names'):
                    assert_rig_survived({'meshes': [source]},
                                        {'meshes': [mesh(source['name'], source['armature'], [])]}, source['name'])

    def test_all_entrypoints_consume_one_policy(self):
        publication = (ROOT / 'system/asset-manager/prepare_real_estate_publication_fbx.py').read_text()
        studio = (ROOT / 'system/control-center/real_estate/studio_sync.py').read_text()
        validator = (ROOT / 'system/studio-plugin/modules/StudioRealEstateRigValidation.luau').read_text()
        self.assertIn('publish_bones_for_mesh(', publication)
        self.assertIn('publish_bones_for_mesh(part)', studio)
        self.assertIn('if #expected == 0 and boneCount > 0 then', validator)
        self.assertIn('if #missing > 0 then', validator)

if __name__ == '__main__':
    unittest.main()
