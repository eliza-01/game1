"""M274: skinned Character FBX import normalizes existing weights without rerigging.

Blender authoring behavior is exercised through a mesh/vertex-group fake; the
real Blender FBX round-trip remains an integration check in Roblox Studio.
"""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

from test_character_rigid_hair_m194 import FakeMesh, HairImportTests
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'control-center'))
from character_core.components import CharacterComponents


class GroupList(list):
    def __init__(self, mesh, names):
        super().__init__()
        self.mesh = mesh
        for name in names:
            self.append(_Group(mesh, len(self), name))

    def get(self, name):
        return next((group for group in self if group.name == name), None)


class _Group:
    def __init__(self, mesh, index, name):
        self.mesh, self.index, self.name = mesh, index, name

    def add(self, indices, weight, mode):
        if mode != 'REPLACE':
            raise AssertionError(mode)
        for index in indices:
            vertex = self.mesh.data.vertices[index]
            entry = next((a for a in vertex.groups if a.group == self.index), None)
            if entry is None:
                vertex.groups.append(SimpleNamespace(group=self.index, weight=weight))
            else:
                entry.weight = weight


def make_head():
    mesh = FakeMesh('human_female_m001_head')
    mesh.vertex_groups = GroupList(mesh, ['root', 'hair_mount', 'other_non_bone'])
    for index, vertex in enumerate(mesh.data.vertices):
        vertex.index = index
        vertex.groups = [
            SimpleNamespace(group=0, weight=0.7587204),
            SimpleNamespace(group=1, weight=0.5058136),
            SimpleNamespace(group=2, weight=0.75),
        ]
    return mesh


def inspect_head(mesh):
    adapter, _bpy, rig, _mesh = HairImportTests().load_adapter(mesh)
    rig.name = 'human_female_armature'
    mesh.modifiers = [SimpleNamespace(type='ARMATURE', object=rig)]
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / 'report.json'
        adapter.main(Path(tmp) / 'author.fbx', report)
        return json.loads(report.read_text())


class AutomaticWeightNormalizationTests(unittest.TestCase):
    def test_sum_1_264534_normalizes_preserving_ratio_non_bones_and_bind_pose(self):
        mesh = make_head()
        report = inspect_head(mesh)
        self.assertEqual(report['part_errors'], [])
        self.assertEqual(len(report['parts']), 1)
        part = report['parts'][0]
        self.assertEqual(part['normalized_vertices'], 3)
        self.assertEqual(part['used_bones'], ['hair_mount', 'root'])
        self.assertEqual(len(part['skeleton']), 2)
        for vertex in mesh.data.vertices:
            by_group = {assignment.group: assignment.weight for assignment in vertex.groups}
            self.assertAlmostEqual(by_group[0] + by_group[1], 1.0, places=6)
            self.assertAlmostEqual(by_group[0]/by_group[1], 0.7587204/0.5058136, places=6)
            self.assertEqual(by_group[2], 0.75)  # non-bone group is not normalized

    def test_previously_valid_skin_does_not_change_or_be_reported(self):
        mesh = make_head()
        for vertex in mesh.data.vertices:
            vertex.groups[0].weight = 0.6
            vertex.groups[1].weight = 0.4
        before = [[(assignment.group, assignment.weight) for assignment in v.groups]
                  for v in mesh.data.vertices]
        report = inspect_head(mesh)
        self.assertEqual(report['parts'][0]['normalized_vertices'], 0)
        self.assertEqual(before, [[(a.group, a.weight) for a in v.groups]
                                  for v in mesh.data.vertices])

    def test_missing_bone_weights_fail_without_partially_mutating_other_vertices(self):
        mesh = make_head()
        mesh.data.vertices[2].groups = [SimpleNamespace(group=2, weight=1.0)]
        original = mesh.data.vertices[0].groups[0].weight
        with self.assertRaisesRegex(ValueError, 'vertex 2 has no weights to bones'):
            inspect_head(mesh)
        self.assertEqual(mesh.data.vertices[0].groups[0].weight, original)

    def test_more_than_four_influences_still_fails_and_does_not_discard_bones(self):
        mesh = make_head()
        adapter, _bpy, rig, _ = HairImportTests().load_adapter(mesh)
        rig.name = 'human_female_armature'
        for n in range(3):
            rig.data.bones.append(SimpleNamespace(
                name='extra_bone_'+str(n), parent=None,
                matrix_local=rig.data.bones[0].matrix_local))
        mesh.vertex_groups = GroupList(mesh, ['root', 'hair_mount',
                                               'extra_bone_0', 'extra_bone_1', 'extra_bone_2'])
        for index, vertex in enumerate(mesh.data.vertices):
            vertex.index = index
            vertex.groups = [SimpleNamespace(group=n, weight=0.2) for n in range(5)]
        mesh.modifiers = [SimpleNamespace(type='ARMATURE', object=rig)]
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, '5 bone influences'):
                adapter.main(Path(tmp)/'source.fbx', Path(tmp)/'report.json')
        self.assertEqual(len(mesh.data.vertices[0].groups), 5)

    def test_catalog_inspect_surfaces_normalization_without_partial_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'female.fbx'
            source.write_bytes(b'temporary FBX fixture')
            inspected = inspect_head(make_head())
            store = CharacterComponents(root, analyzer=lambda _root,_source,_out=None: inspected)
            plan = store.inspect(source)
            self.assertFalse(plan['partial_required'])
            self.assertEqual(plan['part_errors'], [])
            self.assertEqual(plan['parts'][0]['normalized_vertices'], 3)

    def test_repeat_inspection_keeps_prepared_content_hash_stable(self):
        first = inspect_head(make_head())['parts'][0]
        second = inspect_head(make_head())['parts'][0]
        self.assertEqual(first['content_sha256'], second['content_sha256'])
        self.assertEqual(first['normalized_vertices'], second['normalized_vertices'])


if __name__ == '__main__':
    unittest.main()
