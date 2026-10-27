"""M131: Real Estate socket/hinge authoring contract & safe Studio assembly."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
sys.path.insert(0, str(ROOT / 'system/asset-manager'))
from real_estate.contracts import assert_rig_survived, validate_analysis, warnings_for_analysis
from real_estate.rig_features import bone_role, feature_warnings, DOOR_HINGE
from real_estate_rig_discovery import find_rig
from real_estate_skin_policy import check_rigid_hinge
from real_estate.store import RealEstateStore
from test_real_estate_m107 import skeleton


IDENTITY = [1.0, 0.0, 0.0, 0.0,
            0.0, 1.0, 0.0, 0.0,
            0.0, 0.0, 1.0, 0.0,
            0.0, 0.0, 0.0, 1.0]

HOUSE = ('chimney_01_socket', 'elevator_01_socket',
         'house_floor_01_spawn_01_socket', 'house_floor_02_spawn_01_socket',
         'chest_01_socket', 'land_spawn_01_socket')
DOOR = ('door_01_handle_inside_socket', 'door_01_handle_outside_socket',
        'door_01_padlock_01_socket')


def modern():
    source = skeleton()
    house, door = source['meshes']
    house['bones'] = [{'name': b, 'parent': '', 'matrixLocal': IDENTITY} for b in HOUSE]
    house['influencedBones'] = []
    door['bones'] = [{'name': DOOR_HINGE, 'parent': '', 'matrixLocal': IDENTITY}] + [
        {'name': b, 'parent': DOOR_HINGE, 'matrixLocal': IDENTITY} for b in DOOR]
    door['influencedBones'] = [DOOR_HINGE]
    return source


class SocketContractM131(unittest.TestCase):
    def test_new_house_and_door_features_are_accepted_without_legacy_advisories(self):
        source = modern()
        self.assertIs(validate_analysis(source), source)
        self.assertEqual(warnings_for_analysis(source), [])
        self.assertEqual(bone_role('door', DOOR_HINGE), 'hinge')
        self.assertEqual(bone_role('door', DOOR[0]), 'socket')
        self.assertEqual(bone_role('house', HOUSE[0]), 'socket')
        self.assertEqual(bone_role('chest_01', 'lid_bone'), 'bone')

    def test_broken_parentage_or_nonroot_hinge_is_warning_not_silent_acceptance(self):
        source = modern()
        source['meshes'][1]['bones'][1]['parent'] = ''
        self.assertIn('door_socket_outside_hinge', {w['code'] for w in warnings_for_analysis(source)})
        source['meshes'][1]['bones'][0]['parent'] = DOOR[1]
        self.assertIn('door_hinge_not_root', {w['code'] for w in warnings_for_analysis(source)})

    def test_incorrect_hinge_hierarchy_requires_explicit_warning_ack_on_registration(self):
        with tempfile.TemporaryDirectory(prefix='game1-m131-') as directory:
            root = Path(directory)
            incoming = root / 'incoming'
            incoming.mkdir()
            fbx = incoming / 'house_level4_01.fbx'
            fbx.write_bytes(b'unit-test-fbx')
            textures = {}
            for part in ('house', 'door'):
                texture = incoming / f'{part}.png'
                texture.write_bytes(b'unit-image')
                textures[part] = str(texture)
            source = modern()
            source['meshes'][1]['bones'][1]['parent'] = ''
            store = RealEstateStore(root)
            payload = {'sourcePath': str(fbx), 'houseType': 'house', 'level': 4,
                       'variant': '01', 'textures': textures}
            with patch('real_estate.store.inspect', return_value=source):
                with self.assertRaisesRegex(ValueError, 'optional rig warnings'):
                    store.register(payload)
                row = store.register({**payload, 'acceptWarnings': True})
            self.assertEqual(row['slug'], 'house_level4_01')
            self.assertIn('door_socket_outside_hinge',
                          {w['code'] for w in store.get(row['slug'])['rigWarnings']})

    def test_socket_weights_not_assigned_to_door_mesh(self):
        source = modern()
        source['meshes'][1]['influencedBones'].append(DOOR[0])
        self.assertIn('door_socket_deforms_mesh', {w['code'] for w in feature_warnings(source)})
        source['meshes'][1]['influencedBones'] = []
        self.assertIn('door_hinge_unweighted', {w['code'] for w in feature_warnings(source)})

    def test_hinge_skin_preservation_does_not_change_any_vertex_weights(self):
        groups = [{DOOR_HINGE: 1.0} for _ in range(1968)]
        original = json.dumps(groups)
        report = check_rigid_hinge(groups, {DOOR_HINGE, *DOOR})
        self.assertEqual(json.dumps(groups), original)
        self.assertEqual(report['modifiedVertexCount'], 0)
        self.assertEqual(report['protectedVertexCount'], 1968)
        for weights in ({DOOR_HINGE: .8}, {DOOR_HINGE:.8,DOOR[0]:.2},
                        {DOOR[0]:1.0}):
            with self.assertRaisesRegex(ValueError, 'weight 1.0'):
                check_rigid_hinge([weights], {DOOR_HINGE, *DOOR})

    def test_staged_import_requires_weighted_hinge_but_not_unweighted_child_sockets(self):
        expected = modern()
        staged = {'meshes': [json.loads(json.dumps(expected['meshes'][1]))]}
        assert_rig_survived(expected, staged, 'door')
        staged['meshes'][0]['influencedBones'] = []
        with self.assertRaisesRegex(ValueError, 'lost weighted bone'):
            assert_rig_survived(expected, staged, 'door')
        staged['meshes'][0]['influencedBones'] = [DOOR_HINGE]
        staged['meshes'][0]['bones'].pop()
        with self.assertRaisesRegex(ValueError, 'changed bone names'):
            assert_rig_survived(expected, staged, 'door')

    def test_rig_discovery_does_not_guess_by_name(self):
        rig = SimpleNamespace(name='door_armature', type='ARMATURE')
        mesh = SimpleNamespace(name='door', type='MESH', parent=None, modifiers=[])
        fake = SimpleNamespace(context=SimpleNamespace(scene=SimpleNamespace(objects=[mesh,rig])))
        self.assertIsNone(find_rig(fake, mesh, 'door'))
        mesh.parent = rig
        self.assertIs(find_rig(fake, mesh, 'door'), rig)

    def test_asset_manager_and_studio_use_one_rigid_movement_path(self):
        script = (ROOT / 'system/asset-manager/prepare_real_estate_publication_fbx.py').read_text()
        studio = (ROOT / 'system/studio-plugin/modules/StudioRealEstateModel.luau').read_text()
        js = (ROOT / 'system/control-center/static/real-estate.js').read_text()
        self.assertIn('check_rigid_hinge(', script)
        self.assertIn('if part == \'door\' and HINGE in names:', script)
        self.assertIn('assembly.WorldPivot = hinge.TransformedWorldCFrame', studio)
        self.assertIn('Game1DoorClosedLocalPivot', studio)
        self.assertIn('DoorAssembly', studio)
        self.assertNotIn('hinge.Transform =', studio)
        self.assertIn("return 'hinge'", js)
        self.assertIn('realEstateRigMode', js)


if __name__ == '__main__':
    unittest.main()
