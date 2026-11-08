"""M266: Location FBX round-trip permits new/split meshes, not damaged Bones."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'system/asset-manager'
sys.path.insert(0, str(ASSETS))
from location_rig_contract import assert_bone_rest_roundtrip, validate

IDENTITY = [1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1.]


def mesh(name, size):
    return SimpleNamespace(name=name, type='MESH',
        data=SimpleNamespace(vertices=[SimpleNamespace(groups=[])] * size, materials=[]),
        vertex_groups=[])


def rig(matrix):
    bone = SimpleNamespace(name='base', parent=None,
        matrix_local=[matrix[i:i + 4] for i in range(0, 16, 4)])
    return SimpleNamespace(name='tree_rig', type='ARMATURE',
        data=SimpleNamespace(bones=[bone]))


def load(name, bpy, deps):
    spec = importlib.util.spec_from_file_location('m266_' + name, ASSETS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    with mock.patch.dict(sys.modules, {'bpy': bpy, **deps}):
        spec.loader.exec_module(module)
    return module


class LocationRoundTripM266(unittest.TestCase):
    def test_manifest_hash_is_a_revision_fingerprint_not_a_gate(self):
        bones = [{'name':'base','parent':'','matrix':IDENTITY}]
        original = validate([{'name':'rig_carrier','vertices':3},
                             {'name':'tree','vertices':1800}], bones)
        split = validate([{'name':'rig_carrier','vertices':3},
                          {'name':'tree','vertices':1000},
                          {'name':'branches','vertices':900}], bones)
        self.assertNotEqual(original['structuralHash'], split['structuralHash'])
        assert_bone_rest_roundtrip(original['bones'], split['bones'])

    def test_numeric_tolerance_parent_and_bone_set(self):
        bones = [{'name':'base', 'parent':'', 'matrix':IDENTITY},
                 {'name':'leaf', 'parent':'base', 'matrix':IDENTITY}]
        assert_bone_rest_roundtrip(bones,
            [dict(bones[0], matrix=[1.00002] + IDENTITY[1:]), bones[1]])
        with self.assertRaisesRegex(ValueError, 'Bone rest pose: base'):
            assert_bone_rest_roundtrip(bones,
                [dict(bones[0], matrix=[1.01] + IDENTITY[1:]), bones[1]])
        with self.assertRaisesRegex(ValueError, 'Bone parent: leaf'):
            assert_bone_rest_roundtrip(bones, [bones[0], dict(bones[1], parent='')])
        with self.assertRaisesRegex(ValueError, 'Bone set'):
            assert_bone_rest_roundtrip(bones, bones[:1])

    def test_publication_records_output_mesh_inventory_not_input(self):
        bpy = types.ModuleType('bpy')
        scene = SimpleNamespace(objects=[])
        bpy.context = SimpleNamespace(scene=scene)
        source_parts = [mesh('tree', 1800)]
        output_parts = [mesh('trunk', 1000), mesh('branches', 900), mesh('col_mesh', 80)]
        bpy.ops = SimpleNamespace(import_scene=SimpleNamespace(
            fbx=lambda *, filepath, use_anim: scene.objects.__setitem__(slice(None),
                output_parts if filepath.endswith('staged.fbx') else source_parts)))
        pub = types.ModuleType('model_publication')
        pub.clean_scene = scene.objects.clear
        pub.linked_meshes = lambda _: []
        pub.prepare_rig = lambda *_: self.fail('unexpected rig in static FBX')
        pub.rest_snapshot = lambda _: {}
        pub.assert_skin_complete = lambda *_: None
        pub.export_model = lambda dest, *_a, **_kw: dest.write_bytes(b'fbx')
        module = load('prepare_model_publication_fbx', bpy, {'model_publication':pub})
        with tempfile.TemporaryDirectory() as d:
            source, staged, report = (Path(d)/s for s in ('source.fbx','staged.fbx','report.json'))
            source.write_bytes(b'source')
            module.main(source, staged, report, 'geometry_only')
            result = json.loads(report.read_text())
        self.assertEqual(result['locationRigManifest']['rigKind'], 'static')
        self.assertEqual([p['name'] for p in result['locationRigManifest']['parts']],
                         ['branches', 'col_mesh', 'trunk'])
        self.assertEqual(result['materialSlots'], 0)

    def test_skinned_publication_accepts_split_mesh_without_altering_bones(self):
        bpy = types.ModuleType('bpy')
        scene = SimpleNamespace(objects=[])
        bpy.context = SimpleNamespace(scene=scene)
        before = [rig(IDENTITY), mesh('rig_carrier',3), mesh('tree',1800)]
        after = [rig([1.00002] + IDENTITY[1:]), mesh('rig_carrier',3),
                 mesh('tree',1000), mesh('branches',900)]
        for objects in (before, after):
            for obj in objects:
                if obj.type != 'MESH':
                    continue
                obj.vertex_groups = [SimpleNamespace(index=0, name='base')]
                for vertex in obj.data.vertices:
                    vertex.groups = [SimpleNamespace(group=0, weight=1.0)]
        bpy.data = SimpleNamespace(objects={'tree_rig':after[0]})
        bpy.ops = SimpleNamespace(import_scene=SimpleNamespace(
            fbx=lambda *, filepath, use_anim: scene.objects.__setitem__(slice(None),
                after if filepath.endswith('staged.fbx') else before)))
        pub = types.ModuleType('model_publication')
        pub.clean_scene = scene.objects.clear
        pub.linked_meshes = lambda _: [o for o in scene.objects if o.type == 'MESH']
        pub.prepare_rig = lambda *_: self.fail('Location must not rewrite skin during upload')
        pub.assert_skin_complete = lambda *_: None
        pub.rest_snapshot = lambda armature: {
            'base':{'parent':'', 'matrix':tuple(v for row in armature.data.bones[0].matrix_local for v in row)}}
        pub.export_model = lambda dest, *_a, **_kw: dest.write_bytes(b'fbx')
        module = load('prepare_model_publication_fbx', bpy, {'model_publication':pub})
        with tempfile.TemporaryDirectory() as d:
            source, staged, report = (Path(d)/s for s in ('source.fbx','staged.fbx','report.json'))
            source.write_bytes(b'source')
            module.main(source, staged, report, 'geometry_only')
            result = json.loads(report.read_text())
        manifest = result['locationRigManifest']
        self.assertEqual(manifest['rigKind'], 'skinned')
        self.assertEqual([p['name'] for p in manifest['parts']],
                         ['branches', 'rig_carrier', 'tree'])
        self.assertEqual(result['rigs']['tree_rig']['status'], 'validated_authored_skin')

    def test_canonical_authoring_allows_extra_visual_mesh_and_rest_drift(self):
        bpy = types.ModuleType('bpy')
        scene = SimpleNamespace(objects=[])
        bpy.context = SimpleNamespace(scene=scene)
        source_objects = [rig(IDENTITY), mesh('rig_carrier',3), mesh('tree',1800)]
        output_objects = [rig([1.00002] + IDENTITY[1:]), mesh('rig_carrier',3),
                          mesh('tree',1000), mesh('branches',900)]
        bpy.ops = SimpleNamespace(import_scene=SimpleNamespace(
            fbx=lambda *, filepath, use_anim: scene.objects.__setitem__(slice(None),
                output_objects if filepath.endswith('canonical.fbx') else source_objects)))
        pub = types.ModuleType('model_publication')
        pub.clean_scene = scene.objects.clear
        pub.linked_meshes = lambda _: [o for o in scene.objects if o.type == 'MESH']
        pub.prepare_rig = lambda *_: {'status':'validated'}
        pub.assert_skin_complete = lambda *_: None
        pub.export_model = lambda dest, *_a, **_kw: dest.write_bytes(b'fbx')
        carrier = types.ModuleType('blender_rig_carrier')
        carrier.create_rig_carrier = lambda _: self.fail('carrier already present')
        module = load('location_rig_authoring_fbx', bpy,
                      {'model_publication':pub, 'blender_rig_carrier':carrier})
        with tempfile.TemporaryDirectory() as d:
            source, staged, report = (Path(d)/s for s in ('source.fbx','canonical.fbx','manifest.json'))
            source.write_bytes(b'source')
            module.main(source, staged, report)
            result = json.loads(report.read_text())
        self.assertEqual([p['name'] for p in result['parts']],
                         ['branches', 'rig_carrier', 'tree'])
        self.assertEqual(result['skinPreparation']['status'], 'validated')


if __name__ == '__main__':
    unittest.main()
