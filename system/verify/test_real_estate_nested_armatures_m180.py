"""M180: authored nested armatures remain separate through inspection/publication."""
from __future__ import annotations

import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/asset-manager'))
sys.path.insert(0, str(ROOT / 'system/control-center'))
from real_estate_fbx_hierarchy import authored_rigs, AuthoredRigs
from real_estate_import_rigs import restore_authored_rigs
from real_estate_rig_discovery import find_rig
from real_estate.contracts import warnings_for_analysis


def minimal_fbx(wide=False):
    """Build real binary FBX node headers/props, not a fake JSON interpretation."""
    header = 25 if wide else 13
    fmt = '<QQQB' if wide else '<IIIB'

    def prop(value):
        if isinstance(value, int):
            return b'L' + struct.pack('<q', value)
        encoded = value.encode('utf8')
        return b'S' + struct.pack('<I', len(encoded)) + encoded

    def node(name, values=(), children=(), start=27):
        raw_name = name.encode('utf8')
        payload = b''.join(prop(value) for value in values)
        child_data = b''
        for child_name, child_values, descendants in children:
            child_data += node(child_name, child_values, descendants,
                               start + header + len(raw_name) + len(payload) + len(child_data))
        if children:
            child_data += bytes(header)
        end = start + header + len(raw_name) + len(payload) + len(child_data)
        return struct.pack(fmt, end, len(values), len(payload), len(raw_name)) + raw_name + payload + child_data

    def model(number, name, kind):
        return ('Model', [number, name + '\x00\x01Model', kind], [])

    objects = [model(1, 'house_armature', 'Null'), model(2, 'door_armature', 'Null'),
               model(3, 'house_socket', 'LimbNode'), model(4, 'door_01_hinge_socket', 'LimbNode'),
               model(5, 'door_handle', 'LimbNode'), model(6, 'house', 'Mesh'),
               model(7, 'door', 'Mesh'), model(8, 'col_mesh', 'Mesh'),
               ('Geometry', [11, 'house_mesh\x00\x01Geometry', 'Mesh'], []),
               ('Geometry', [12, 'door_mesh\x00\x01Geometry', 'Mesh'], []),
               ('Geometry', [13, 'col_mesh\x00\x01Geometry', 'Mesh'], []),
               ('Deformer', [21, 'house_skin\x00\x01Deformer', 'Skin'], []),
               ('Deformer', [22, 'door_skin\x00\x01Deformer', 'Skin'], []),
               ('Deformer', [31, 'house_cluster\x00\x01Deformer', 'Cluster'], []),
               ('Deformer', [32, 'door_cluster\x00\x01Deformer', 'Cluster'], [])]
    edges = [(2, 1), (3, 1), (4, 2), (5, 4), (8, 1),
             (11, 6), (12, 7), (13, 8), (21, 11), (22, 12),
             (31, 21), (32, 22), (3, 31), (4, 32)]
    roots = [('Objects', [], objects), ('Connections', [], [('C', ['OO', a, b], []) for a, b in edges])]
    data = b'Kaydara FBX Binary  \x00\x1a\x00' + struct.pack('<I', 7500 if wide else 7400)
    for name, values, children in roots:
        data += node(name, values, children, len(data))
    return data + bytes(header)


class TestNestedArmatureMetadata(unittest.TestCase):
    def test_nested_objects_are_not_interpreted_as_parent_bones(self):
        for wide in (False, True):
            with self.subTest(fbx_version='7500' if wide else '7400'), tempfile.TemporaryDirectory() as folder:
                source = Path(folder) / 'house_level5_01.fbx'
                original = minimal_fbx(wide)
                source.write_bytes(original)
                hierarchy = authored_rigs(source)
                self.assertEqual(hierarchy.nested, {'door_armature'})
                self.assertEqual(hierarchy.bones['house_armature'], {'house_socket'})
                self.assertEqual(hierarchy.bones['door_armature'], {'door_01_hinge_socket', 'door_handle'})
                self.assertEqual(hierarchy.parents['door_armature'],
                                 {'door_01_hinge_socket': '', 'door_handle': 'door_01_hinge_socket'})
                self.assertEqual(hierarchy.mesh_rigs,
                                 {'house': 'house_armature', 'door': 'door_armature', 'col_mesh': 'house_armature'})
                self.assertEqual(source.read_bytes(), original)

    def test_shared_house_armature_is_not_a_registration_warning(self):
        analysis = {'meshes': [
            {'name': 'house', 'armature': 'house_armature', 'bones': []},
            {'name': 'col_mesh', 'armature': 'house_armature', 'bones': []},
            {'name': 'door', 'armature': 'door_armature', 'bones': []},
        ]}
        self.assertEqual(warnings_for_analysis(analysis), [])

    def test_inspection_and_preparation_call_the_same_recovery(self):
        for path in ('analyze_real_estate_fbx.py', 'prepare_real_estate_publication_fbx.py'):
            code = (ROOT / 'system/asset-manager' / path).read_text('utf8')
            self.assertIn('from real_estate_import_rigs import restore_authored_rigs', code)
            self.assertIn('restore_authored_rigs(bpy, source)', code)


class Matrix(list):
    def copy(self):
        return Matrix([list(row) for row in self])


class Bone:
    def __init__(self, name, x, parent=None):
        self.name = name
        self.matrix = Matrix([[1, 0, 0, x], [0, 1, 0, 0],
                              [0, 0, 1, 0], [0, 0, 0, 1]])
        self.parent = parent
        self.use_connect = False

    @property
    def matrix_local(self):
        return self.matrix


class Bones:
    def __init__(self, source):
        self.items = list(source)

    def __iter__(self):
        return iter(self.items)

    def __getitem__(self, key):
        return next(bone for bone in self.items if bone.name == key)

    def remove(self, value):
        self.items.remove(value)


class ArmatureData:
    def __init__(self, bones):
        self.bones = Bones(bones)
        self.edit_bones = self.bones

    def copy(self):
        clones = {b.name: Bone(b.name, b.matrix[0][3]) for b in self.bones}
        for bone in self.bones:
            clones[bone.name].parent = clones.get(bone.parent.name) if bone.parent else None
        return ArmatureData(list(clones.values()))


class Modifier:
    type = 'ARMATURE'

    def __init__(self, rig):
        self.object = rig


class FakeModifiers(list):
    def new(self, name, type):
        if type != 'ARMATURE':
            raise ValueError(type)
        modifier = Modifier(None)
        modifier.name = name
        self.append(modifier)
        return modifier


class Mesh:
    type = 'MESH'

    def __init__(self, name, rig):
        self.name = name
        self.parent = None
        self.modifiers = FakeModifiers([Modifier(rig)])
        self.matrix_world = Matrix([[1, 0, 0, 50], [0, 1, 0, 60],
                                    [0, 0, 1, 70], [0, 0, 0, 1]])


class Rig:
    type = 'ARMATURE'

    def __init__(self, name, data, collection):
        self.name = name
        self.data = data
        self.users_collection = [collection]
        self.matrix_world = Matrix([[1, 0, 0, 100], [0, 0, -1, 10],
                                    [0, 1, 0, 20], [0, 0, 0, 1]])

    def select_set(self, state):
        pass


class SceneObjects(list):
    def get(self, name):
        return next((obj for obj in self if obj.name == name), None)


class FakeBpy:
    def __init__(self):
        from types import SimpleNamespace
        self.objects = SceneObjects()
        self.context = SimpleNamespace(scene=SimpleNamespace(objects=self.objects),
                                       view_layer=SimpleNamespace(objects=SimpleNamespace(active=None)))
        collection = SimpleNamespace(objects=SimpleNamespace(link=self.objects.append))
        root = Bone('house_socket', 1)
        phantom = Bone('door_armature', 7)
        hinge = Bone('door_01_hinge_socket', 12, phantom)
        handle = Bone('door_handle', 19, hinge)
        self.rig = Rig('house_armature', ArmatureData([root, phantom, hinge, handle]), collection)
        self.objects.append(self.rig)
        self.house = Mesh('house', self.rig)
        self.door = Mesh('door', self.rig)
        self.objects.extend((self.house, self.door))
        self.data = SimpleNamespace(objects=SimpleNamespace(get=self.objects.get, new=lambda name, data: Rig(name, data, collection)))
        self.ops = SimpleNamespace(object=SimpleNamespace(select_all=lambda **kw: None,
                                                           mode_set=lambda **kw: None))


class TestNestedArmatureSceneRecovery(unittest.TestCase):
    def test_split_preserves_world_and_rest_matrices_and_reroutes_door_skin(self):
        fake = FakeBpy()
        authored = AuthoredRigs(
            bones={'house_armature': frozenset({'house_socket'}),
                   'door_armature': frozenset({'door_01_hinge_socket', 'door_handle'})},
            parents={'house_armature': {'house_socket': ''},
                     'door_armature': {'door_01_hinge_socket': '', 'door_handle': 'door_01_hinge_socket'}},
            mesh_rigs={'house': 'house_armature', 'door': 'door_armature'},
            nested=frozenset({'door_armature'}))
        before_world = fake.door.matrix_world.copy()
        before_armature_world = fake.rig.matrix_world.copy()
        before_hinge = fake.rig.data.bones['door_01_hinge_socket'].matrix.copy()
        with patch('real_estate_import_rigs.authored_rigs', return_value=authored):
            restore_authored_rigs(fake, Path('test.fbx'))
        recovered = fake.objects.get('door_armature')
        self.assertIsNotNone(recovered)
        self.assertEqual({b.name for b in fake.rig.data.bones}, {'house_socket'})
        self.assertEqual({b.name for b in recovered.data.bones}, {'door_01_hinge_socket', 'door_handle'})
        self.assertIsNone(recovered.data.bones['door_01_hinge_socket'].parent)
        self.assertEqual(recovered.data.bones['door_handle'].parent.name, 'door_01_hinge_socket')
        self.assertEqual(recovered.data.bones['door_01_hinge_socket'].matrix, before_hinge)
        self.assertEqual(recovered.matrix_world, before_armature_world)
        self.assertEqual(fake.door.matrix_world, before_world)
        self.assertIs(fake.house.modifiers[0].object, fake.rig)
        self.assertIs(fake.door.modifiers[0].object, recovered)

    def test_missing_imported_modifier_is_restored_from_fbx_skin_owner(self):
        # M181 regression: Blender can import the skinned door as either an
        # unlinked mesh or a child of the wrongly collapsed house armature.
        # M180 detached the latter but never created the missing modifier.
        for parented_to_collapsed_rig in (False, True):
            with self.subTest(parented=parented_to_collapsed_rig):
                fake = FakeBpy()
                fake.door.modifiers = FakeModifiers()
                fake.door.parent = fake.rig if parented_to_collapsed_rig else None
                before_world = fake.door.matrix_world.copy()
                hierarchy = AuthoredRigs(
                    bones={'house_armature': frozenset({'house_socket'}),
                           'door_armature': frozenset({'door_01_hinge_socket', 'door_handle'})},
                    parents={'house_armature': {'house_socket': ''},
                             'door_armature': {'door_01_hinge_socket': '',
                                               'door_handle': 'door_01_hinge_socket'}},
                    mesh_rigs={'house': 'house_armature', 'door': 'door_armature'},
                    nested=frozenset({'door_armature'}))
                with patch('real_estate_import_rigs.authored_rigs', return_value=hierarchy):
                    restore_authored_rigs(fake, Path('test.fbx'))
                    # Inspect and Publish can both reuse the same recovery;
                    # rerunning it must not duplicate modifiers or rig objects.
                    restore_authored_rigs(fake, Path('test.fbx'))
                door_rig = fake.objects.get('door_armature')
                self.assertIs(find_rig(fake, fake.door, 'door'), door_rig)
                self.assertEqual(len(fake.door.modifiers), 1)
                self.assertEqual(fake.door.modifiers[0].name, 'Game1RecoveredFBXRig')
                self.assertIsNone(fake.door.parent)
                self.assertEqual(fake.door.matrix_world, before_world)
                self.assertIs(find_rig(fake, fake.house, 'house'), fake.rig)
                # This is what removes both observed inspection warnings.
                sample = {'meshes': [
                    {'name': 'house', 'armature': find_rig(fake, fake.house, 'house').name, 'bones': []},
                    {'name': 'door', 'armature': find_rig(fake, fake.door, 'door').name, 'bones': []},
                ], 'unassignedArmatures': []}
                self.assertEqual(warnings_for_analysis(sample), [])

    def test_ambiguous_imported_armature_modifiers_are_rejected(self):
        fake = FakeBpy()
        fake.door.modifiers = FakeModifiers([Modifier(fake.rig), Modifier(fake.rig)])
        hierarchy = AuthoredRigs(
            bones={'house_armature': frozenset({'house_socket'}),
                   'door_armature': frozenset({'door_01_hinge_socket', 'door_handle'})},
            parents={'house_armature': {'house_socket': ''},
                     'door_armature': {'door_01_hinge_socket': '', 'door_handle': 'door_01_hinge_socket'}},
            mesh_rigs={'house': 'house_armature', 'door': 'door_armature'},
            nested=frozenset({'door_armature'}))
        with patch('real_estate_import_rigs.authored_rigs', return_value=hierarchy):
            with self.assertRaisesRegex(RuntimeError, 'multiple armature modifiers'):
                restore_authored_rigs(fake, Path('test.fbx'))

    def test_non_nested_fbx_is_left_unchanged(self):
        fake = FakeBpy()
        with patch('real_estate_import_rigs.authored_rigs', return_value=AuthoredRigs({}, {}, {}, frozenset())):
            restore_authored_rigs(fake, Path('test.fbx'))
        self.assertEqual(len(fake.objects), 3)
        self.assertIs(fake.door.modifiers[0].object, fake.rig)


if __name__ == '__main__':
    unittest.main()
