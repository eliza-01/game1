"""M194: rigid hairstyle belongs to hair_mount by authored object pivot."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'control-center'))
from character_core.part_names import rigid_pivot_mount_for_part
from character_core.components import CharacterComponents


class FakeMatrix:
    def __iter__(self):
        return iter([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])

    def __matmul__(self, other):
        return self

    def copy(self):
        return self


class FakeMesh:
    type = 'MESH'

    def __init__(self, name='hair_03_common', weights=False):
        self.name = name
        self.matrix_world = FakeMatrix()
        self.parent = SimpleNamespace(name='human_armature')
        self.vertex_groups = []
        groups = [SimpleNamespace(weight=1.0, group=0)] if weights else []
        self.data = SimpleNamespace(
            vertices=[SimpleNamespace(co=(0, 0, 0), groups=groups),
                      SimpleNamespace(co=(1, 0, 0), groups=[]),
                      SimpleNamespace(co=(0, 1, 0), groups=[])],
            polygons=[SimpleNamespace(vertices=(0, 1, 2), material_index=0, use_smooth=True)],
            uv_layers=[], materials=[],
        )
        self.modifiers = []


class HairImportTests(unittest.TestCase):
    def load_adapter(self, mesh=None, mount=True):
        mesh = mesh or FakeMesh()
        names = ['root', 'hair_mount'] if mount else ['root']
        rig = SimpleNamespace(type='ARMATURE', name='human_armature', matrix_world=FakeMatrix(),
                              data=SimpleNamespace(bones=[SimpleNamespace(name=name, parent=None,
                                  matrix_local=FakeMatrix(), head_local=(0, 0, 0)) for name in names],
                                  pose_position='POSE'))
        bpy = ModuleType('bpy')
        bpy.ops = SimpleNamespace(object=SimpleNamespace(select_all=MagicMock(), delete=MagicMock()),
                                  import_scene=SimpleNamespace(fbx=MagicMock()))
        bpy.context = SimpleNamespace(scene=SimpleNamespace(objects=[rig, mesh],
                         collection=SimpleNamespace(objects=SimpleNamespace(link=MagicMock()))),
                         view_layer=SimpleNamespace(update=MagicMock()))
        bpy.data = SimpleNamespace(objects=SimpleNamespace(remove=MagicMock()))
        mathutils = ModuleType('mathutils')
        mathutils.Vector = lambda value: value
        spec = importlib.util.spec_from_file_location('character_components_fbx_m194_test',
                                                     ROOT / 'asset-manager/character_components_fbx.py')
        adapter = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'bpy': bpy, 'mathutils': mathutils}):
            spec.loader.exec_module(adapter)
        return adapter, bpy, rig, mesh

    def test_slot_policy_is_explicit_not_generic_rigless_fallback(self):
        self.assertEqual(rigid_pivot_mount_for_part('hair_03_common'), 'hair_mount')
        self.assertEqual(rigid_pivot_mount_for_part('hair_03_male'), 'hair_mount')
        for name in ('head_01_male', 'newborn_upper', 'eyes_01', 'hair_fake', 'hat_01'):
            self.assertEqual(rigid_pivot_mount_for_part(name), '')

    def test_blender_report_emits_rigid_hair_without_bone_bind(self):
        adapter, _bpy, _rig, mesh = self.load_adapter()
        with tempfile.TemporaryDirectory() as temp:
            report = Path(temp) / 'report.json'
            adapter.main(Path(temp) / 'in.fbx', report)
            data = json.loads(report.read_text())
        self.assertEqual(data['armature'], 'human_armature')
        self.assertEqual(len(data['parts']), 1)
        hair = data['parts'][0]
        self.assertEqual(hair['name'], 'hair_03_common')
        self.assertEqual(hair['armature'], '')
        self.assertEqual(hair['skeleton'], [])
        self.assertEqual(hair['used_bones'], [])
        self.assertEqual(hair['attachment'], 'hair_mount')
        self.assertEqual(hair['attachment_mode'], 'pivot')
        self.assertEqual(mesh.parent.name, 'human_armature')  # analysis does not edit artist source

    def test_blender_rejects_other_unskinned_parts_and_invalid_hair(self):
        for name, weights, mount, message in (
            ('head_01_male', False, True, 'one Armature modifier'),
            ('hair_03_common', True, True, 'deform weights'),
            ('hair_03_common', False, False, 'hair_mount'),
        ):
            with self.subTest(name=name, weights=weights, mount=mount):
                adapter, *_ = self.load_adapter(FakeMesh(name, weights), mount)
                with tempfile.TemporaryDirectory() as temp:
                    with self.assertRaisesRegex(ValueError, message):
                        adapter.main(Path(temp) / 'in.fbx', Path(temp) / 'report.json')

    def test_rigid_export_preserves_world_pivot_without_armature(self):
        source = FakeMesh()
        adapter, bpy, *_ = self.load_adapter(source)
        cloned = FakeMesh('copy')
        source.data.copy = MagicMock(return_value=cloned.data)
        source.copy = MagicMock(return_value=cloned)
        with patch.object(adapter, 'export') as export:
            adapter.export_rigid_pivot_mesh(source, Path('hair_03_common.fbx'))
            export.assert_called_once()
            path, objects = export.call_args.args
            self.assertEqual(path.name, 'hair_03_common.fbx')
            self.assertEqual(objects, [cloned])
            self.assertIsNone(cloned.parent)
            self.assertIs(cloned.matrix_world, source.matrix_world)
            self.assertEqual(cloned.name, 'hair_03_common')
            self.assertEqual(source.name, 'hair_03_common')
            bpy.data.objects.remove.assert_called_once_with(cloned, do_unlink=True)

    def test_registry_accepts_pivot_hair_with_no_skin_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'human.fbx'
            source.write_bytes(b'fixture')
            bones = [dict(name='root', parent='', matrix=[1, 0, 0, 0] * 4),
                     dict(name='hair_mount', parent='root', matrix=[1, 0, 0, 0] * 4)]
            row = dict(name='hair_03_common', armature='', skeleton=[], used_bones=[],
                       attachment='hair_mount', attachment_mode='pivot', vertices=3, triangles=1,
                       content_sha256='hair', materials=[])
            def analyze(_root, _source, output=None):
                if output:
                    output.mkdir(parents=True, exist_ok=True)
                    (output / 'rig.fbx').write_bytes(b'core')
                    (output / 'hair_03_common.fbx').write_bytes(b'hair')
                return dict(armature='human_armature', bones=bones, parts=[row])
            store = CharacterComponents(root, analyzer=analyze)
            plan = store.inspect(source)
            self.assertEqual(plan['parts'][0]['attachment_mode'], 'pivot')
            store.register(plan['token'], [])
            hair = store.get('part', 'hair_03_common')
            self.assertEqual(json.loads(hair['metadata_json'])['attachment_mode'], 'pivot')
            self.assertTrue((root / hair['prepared_path']).is_file())
            self.assertEqual((root / hair['prepared_path']).read_bytes(), b'hair')
            # Reject a tampered inspect response: pivot is only for rigless hair.
            row['name'] = 'head_01_male'
            with self.assertRaisesRegex(ValueError, 'invalid rigid hair'):
                store.inspect(source)

    def test_runtime_keeps_socket_mode_and_aligns_rigid_pivot(self):
        source = (ROOT.parent / 'src/server/character/CharacterAssemblyBuilder.luau').read_text()
        self.assertIn('mesh:PivotTo(target.WorldCFrame)', source)
        self.assertIn('mesh.CFrame:ToObjectSpace(target.WorldCFrame)', source)
        self.assertIn('local socket = assert(incoming[part.socket_bone]', source)
        self.assertIn('joint.Attachment0 = target', source)
        self.assertIn('joint.Attachment1 = anchor', source)


if __name__ == '__main__':
    unittest.main()
