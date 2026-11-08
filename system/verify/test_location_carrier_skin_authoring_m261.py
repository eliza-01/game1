"""M261: authored Location skin uses Character normalization; upload never rewrites it.

Blender itself is unavailable in pure unit tests. The tests exercise the real
weight planner through a minimal vertex-group adapter and the two Blender entry
point contracts with fake Blender scene operations.
"""
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
ASSETS = ROOT / 'system' / 'asset-manager'
sys.path.insert(0, str(ASSETS))


class Identity:
    def __matmul__(self, vector):
        return vector


class Group:
    def __init__(self, collection, name):
        self._collection = collection
        self.name = name
        self.index = len(collection.items)

    def add(self, indices, weight, mode):
        assert mode == 'REPLACE'
        for index in indices:
            vertex = self._collection.mesh.data.vertices[index]
            vertex.groups[:] = [g for g in vertex.groups if g.group != self.index]
            vertex.groups.append(SimpleNamespace(group=self.index, weight=weight))

    def remove(self, indices):
        for index in indices:
            vertex = self._collection.mesh.data.vertices[index]
            vertex.groups[:] = [g for g in vertex.groups if g.group != self.index]


class Groups:
    def __init__(self, mesh):
        self.mesh = mesh
        self.items = []

    def __iter__(self):
        return iter(self.items)

    def new(self, name):
        group = Group(self, name)
        self.items.append(group)
        return group

    def get(self, name):
        return next((g for g in self.items if g.name == name), None)


class SkinAuthoringTests(unittest.TestCase):
    def _load(self, name, *, bpy=None, **replacements):
        spec = importlib.util.spec_from_file_location('m261_' + name, ASSETS / (name + '.py'))
        module = importlib.util.module_from_spec(spec)
        with mock.patch.dict(sys.modules, {'bpy': bpy or types.ModuleType('bpy'), **replacements}):
            spec.loader.exec_module(module)
        return module

    def _rig_and_visual(self):
        bones = [SimpleNamespace(name='Bone', parent=None, head_local=(0., 0., 0.),
                                 tail_local=(0., 1., 0.), matrix_local=((1., 0., 0., 0.),) * 4,
                                 use_deform=False),
                 SimpleNamespace(name='Bone.001', parent=None, head_local=(10., 0., 0.),
                                 tail_local=(10., 1., 0.), matrix_local=((1., 0., 0., 0.),) * 4,
                                 use_deform=False)]
        rig = SimpleNamespace(name='tree_rig', type='ARMATURE', data=SimpleNamespace(bones=bones),
                              matrix_world=Identity())
        vertices = [SimpleNamespace(index=i, co=(10., 0., 0.) if i == 80 else (0., 0., 0.),
                                    groups=[]) for i in range(81)]
        mesh = SimpleNamespace(name='christmas_tree_01', type='MESH', data=SimpleNamespace(vertices=vertices),
                               matrix_world=Identity(), parent=rig, modifiers=[])
        mesh.vertex_groups = Groups(mesh)
        mesh.vertex_groups.new('Bone').add(range(80), 1.0, 'REPLACE')
        # Vertex 80 has no influence, precisely the failure reported by the user.
        return rig, mesh

    def test_shared_character_planner_repairs_missing_vertex_before_authoring_export(self):
        module = self._load('model_publication')
        rig, visual = self._rig_and_visual()
        with self.assertRaisesRegex(ValueError, 'vertex 80'):
            module.assert_skin_complete(rig, [visual])
        before = module.rest_snapshot(rig)
        report = module.prepare_rig(rig, [visual])
        self.assertEqual(report['unweightedVerticesBefore'], 1)
        self.assertEqual(report['unweightedVerticesAfter'], 0)
        module.assert_rest_unchanged(rig, before)
        module.assert_skin_complete(rig, [visual])
        self.assertEqual(len(visual.data.vertices), 81)
        self.assertEqual(visual.data.vertices[0].groups[0].weight, 1.0)
        self.assertEqual(visual.data.vertices[80].groups[0].weight, 1.0)
        self.assertEqual(report['survivingBoneCount'], 2)
        report2 = module.prepare_rig(rig, [visual])
        self.assertEqual(report2['unweightedVerticesBefore'], 0)
        self.assertEqual(report2['patchedBoneCount'], 0)

    def test_location_authoring_normalizes_new_copy_before_export_and_validates_roundtrip(self):
        bpy = types.ModuleType('bpy')
        scene = SimpleNamespace(objects=[])
        bpy.context = SimpleNamespace(scene=scene)
        calls = []
        rig, visual = self._rig_and_visual()
        carrier = SimpleNamespace(name='rig_carrier', type='MESH', parent=rig,
                                  data=SimpleNamespace(vertices=[1, 2, 3]))
        def imp(*, filepath, use_anim):
            calls.append('import')
            scene.objects[:] = [rig, visual] + ([carrier] if filepath.endswith('authored.fbx') else [])
        bpy.ops = SimpleNamespace(import_scene=SimpleNamespace(fbx=imp))
        module = self._load('location_rig_authoring_fbx', bpy=bpy,
                            mathutils=SimpleNamespace(Vector=lambda v:v))
        manifest = {'schemaVersion':2,'structuralHash':'struct','inventoryHash':'inv','boneHash':'bone',
                    'bones':[{'name':name, 'parent':'', 'matrix':[1.,0.,0.,0.]*4}
                             for name in ('Bone', 'Bone.001')]}
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / 'source.fbx'
            output = Path(d) / 'authored.fbx'
            report = Path(d) / 'manifest.json'
            source.write_bytes(b'source remains unchanged')
            def create(*_):
                scene.objects.append(carrier)
                calls.append('carrier')
            def prepare(*_):
                calls.append('prepare')
                return {'unweightedVerticesBefore':1,'unweightedVerticesAfter':0}
            def export(path, objects, **kwargs):
                calls.append('export')
                self.assertEqual(kwargs, {'no_textures':True})
                self.assertEqual(source.read_bytes(), b'source remains unchanged')
                path.write_bytes(b'new authored FBX')
            with mock.patch.object(module,'clean_scene',side_effect=lambda:calls.append('clean')), \
                 mock.patch.object(module,'create_rig_carrier',side_effect=create), \
                 mock.patch.object(module,'describe',return_value=manifest), \
                 mock.patch.object(module,'prepare_rig',side_effect=prepare), \
                 mock.patch.object(module,'export_model',side_effect=export), \
                 mock.patch.object(module,'assert_skin_complete') as validate:
                module.main(source, output, report)
            self.assertEqual(calls.count('prepare'),1)
            self.assertLess(calls.index('carrier'),calls.index('prepare'))
            self.assertLess(calls.index('prepare'),calls.index('export'))
            validate.assert_called_once()
            self.assertEqual(json.loads(report.read_text())['skinPreparation']['unweightedVerticesBefore'],1)
            self.assertEqual(source.read_bytes(),b'source remains unchanged')

    def test_location_publication_only_validates_skin_while_other_domains_prepare(self):
        bpy = types.ModuleType('bpy')
        rig = SimpleNamespace(name='rig',type='ARMATURE', data=SimpleNamespace(bones=[SimpleNamespace(name='Bone')]))
        visual = SimpleNamespace(name='tree', type='MESH', data=SimpleNamespace(materials=[], vertices=[SimpleNamespace(groups=[SimpleNamespace(group=0,weight=1)])]), vertex_groups=[SimpleNamespace(index=0,name='Bone')])
        bpy.context = SimpleNamespace(scene=SimpleNamespace(objects=[rig, visual]))
        bpy.data = SimpleNamespace(objects={'rig':rig})
        bpy.ops = SimpleNamespace(import_scene=SimpleNamespace(fbx=lambda **kw:None))
        module = self._load('prepare_model_publication_fbx', bpy=bpy)
        manifest={'schemaVersion':2,'structuralHash':'same'}
        calls=[]
        for mode, expected in (
            ('geometry_only', ['validate', 'export', 'validate']),
            ('embedded', ['rewrite', 'export', 'validate']),
        ):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as d:
                calls.clear()
                output=Path(d)/'out.fbx'; report=Path(d)/'report.json'
                with mock.patch.object(module, 'clean_scene'), \
                     mock.patch.object(module, 'location_manifest', return_value=manifest), \
                     mock.patch.object(module, 'visual_skin', return_value={}), \
                     mock.patch.object(module, 'snapshot', return_value={'rig': {'Bone':{'parent':'', 'matrix':(0,)*16}}}), \
                     mock.patch.object(module, 'linked_meshes', return_value=[visual]), \
                     mock.patch.object(module, 'assert_skin_complete', side_effect=lambda *_:calls.append('validate')), \
                     mock.patch.object(module, 'prepare_rig', side_effect=lambda *_:calls.append('rewrite') or {'mode':'prepared'}), \
                     mock.patch.object(module, 'export_model', side_effect=lambda *_a,**_k: calls.append('export')):
                    module.main(Path(d)/'source.fbx',output,report,texture_mode=mode)
                self.assertEqual(calls, expected)
                result=json.loads(report.read_text())
                if mode == 'geometry_only':
                    self.assertEqual(result['rigs']['rig']['status'], 'validated_authored_skin')
                    self.assertEqual(result['materialSlots'], 0)
                else:
                    self.assertEqual(result['rigs']['rig']['mode'], 'prepared')


if __name__ == '__main__':
    unittest.main()
