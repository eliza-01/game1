"""M272 compound rigid hair: grouped FBX, one part identity, validated tint channels."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'control-center'))
from character_core.part_names import parse_part, parse_hair_extra, hair_color_channels
from character_core.components import CharacterComponents
from character_core.assemblies import CharacterAssemblies
from character_core.armor import ArmorCatalog
from character_store import CharacterStore
from sqlite_connection import connect
import test_character_rigid_hair_m194 as m194
from test_character_rigid_hair_m194 import FakeMesh

IDENTITY = [1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1.]
ROOT = 'human_female_m004_hair'
EXTRA1 = ROOT + '_extra_01'
EXTRA2 = ROOT + '_extra_02'


class CompoundHairTests(unittest.TestCase):
    def test_extra_is_contained_not_registered_as_part(self):
        self.assertEqual(parse_part(ROOT)['slot'], 'hair')
        self.assertEqual(parse_hair_extra(EXTRA1), dict(root_id=ROOT, channel='extra_01'))
        self.assertIsNone(parse_hair_extra(ROOT + '_extra_00'))
        self.assertIsNone(parse_hair_extra('human_female_m004_head_extra_01'))
        with self.assertRaises(ValueError):
            parse_part(EXTRA1)
        channels = hair_color_channels(dict(name=ROOT, extras=[{'name': EXTRA2}, {'name': EXTRA1}]))
        self.assertEqual(channels, ['primary', 'extra_02', 'extra_01'])
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            hair_color_channels(dict(name=ROOT, extras=[{'name': EXTRA1}, {'name': EXTRA1}]))

    def fake_blender(self, no_rig=False):
        root = FakeMesh(ROOT)
        adapter, bpy, rig, _ = m194.HairImportTests().load_adapter(root)
        extra = FakeMesh(EXTRA1)
        bpy.context.scene.objects.append(extra)
        if no_rig:
            bpy.context.scene.objects.remove(rig)
        return adapter, bpy, root, extra

    def test_blender_reports_one_component_and_rigless_import(self):
        adapter, _, _, _ = self.fake_blender(no_rig=True)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'report.json'
            adapter.main(Path(temp) / 'hair.fbx', path)
            report = json.loads(path.read_text())
        self.assertFalse(report['rig_present'])
        self.assertEqual(report['armature'], 'human_female_armature')
        self.assertEqual(report['bones'], [])
        self.assertEqual(len(report['parts']), 1)
        self.assertEqual(report['parts'][0]['name'], ROOT)
        self.assertEqual([e['name'] for e in report['parts'][0]['extras']], [EXTRA1])
        self.assertEqual(report['parts'][0]['attachment_mode'], 'pivot')

    def test_rigless_extraction_schedules_one_fbx_with_both_meshes(self):
        adapter, _, root, extra = self.fake_blender(no_rig=True)
        # Fake Blender objects must support copy for the temporary export.
        for obj in (root, extra):
            clone = FakeMesh('copy')
            obj.copy = MagicMock(return_value=clone)
            obj.data.copy = MagicMock(return_value=clone.data)
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            with patch.object(adapter, 'export') as exporter:
                adapter.main(folder / 'source.fbx', folder / 'report.json', folder)
            exporter.assert_called_once()
            self.assertEqual(exporter.call_args.args[0], folder / (ROOT + '.fbx'))
            self.assertEqual([obj.name for obj in exporter.call_args.args[1]], [ROOT, EXTRA1])

    def test_blender_rejects_orphan_or_weighted_extra(self):
        adapter, bpy, _, extra = self.fake_blender()
        extra.vertex_groups = [type('Group', (), {'index': 0, 'name': 'root'})()]
        extra.data.vertices[0].groups = [type('Weight', (), {'weight': 1.0, 'group': 0})()]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'report.json'
            with self.assertRaisesRegex(ValueError, 'rigid hair extra cannot have deform weights'):
                # Root is rejected and cannot be silently published on its own.
                adapter.main(Path(temp) / 'hair.fbx', path)
        extra.data.vertices[0].groups = []
        bpy.context.scene.objects = [obj for obj in bpy.context.scene.objects if obj.name != ROOT]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'report.json'
            with self.assertRaisesRegex(ValueError, 'orphan extra'):
                adapter.main(Path(temp) / 'hair.fbx', path)

    def test_blender_export_copies_both_parts_preserves_origin_and_source(self):
        adapter, bpy, root, extra = self.fake_blender(no_rig=True)
        root_copy, extra_copy = FakeMesh('copy_1'), FakeMesh('copy_2')
        root.copy = MagicMock(return_value=root_copy)
        extra.copy = MagicMock(return_value=extra_copy)
        root.data.copy = MagicMock(return_value=root_copy.data)
        extra.data.copy = MagicMock(return_value=extra_copy.data)
        with patch.object(adapter, 'export') as exporter:
            adapter.export_rigid_pivot_mesh(root, Path('out.fbx'), [extra])
        exporter.assert_called_once()
        self.assertEqual(exporter.call_args.args[1], [root_copy, extra_copy])
        self.assertEqual((root_copy.name, extra_copy.name), (ROOT, EXTRA1))
        self.assertIsNone(root_copy.parent)
        self.assertIsNone(extra_copy.parent)
        self.assertEqual((root.name, extra.name), (ROOT, EXTRA1))
        self.assertEqual(bpy.data.objects.remove.call_count, 2)

    def setUpCatalog(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        src = root / 'hair.fbx'
        src.write_bytes(b'v1')
        bones = [dict(name='root', parent='', matrix=IDENTITY),
                 dict(name='hair_mount', parent='root', matrix=IDENTITY)]
        head_name = 'human_female_m001_head'
        version = {'extra': 'v1'}

        def analyzer(_root, _source, output=None):
            if output:
                output.mkdir(parents=True, exist_ok=True)
                (output / (ROOT + '.fbx')).write_bytes(version['extra'].encode())
            row = dict(name=ROOT, armature='', attachment='hair_mount', attachment_mode='pivot',
                       skeleton=[], used_bones=[], vertices=3, triangles=1,
                       content_sha256='sha_' + version['extra'], extras=[
                           dict(name=EXTRA1, content_sha256=version['extra'], vertices=3, triangles=1)])
            return dict(armature='human_armature', rig_present=False, bones=[], parts=[row], part_errors=[])

        def rig_analyzer(_root, _source, output=None):
            if output:
                output.mkdir(parents=True, exist_ok=True)
                (output / 'rig.fbx').write_bytes(b'core')
                (output / (head_name + '.fbx')).write_bytes(b'head')
            return dict(armature='human_armature', rig_present=True, bones=copy.deepcopy(bones),
                        parts=[dict(name=head_name, armature='human_armature', skeleton=copy.deepcopy(bones),
                                    used_bones=['root'], vertices=3, triangles=1, content_sha256='head')],
                        part_errors=[])

        components = CharacterComponents(root, analyzer=rig_analyzer)
        rig_plan = components.inspect(src)
        components.register(rig_plan['token'], [], new_parts=[head_name])
        with connect(components.db) as db:
            db.execute("UPDATE character_component_records SET model_asset_id='123456',published_revision=revision")
        components.analyze = analyzer
        components.analyze_rig = rig_analyzer
        self.root = root
        self.source = src
        self.components = components
        self.version = version
        self.head_name = head_name

    def test_rigless_catalog_single_record_and_changed_extra_new_revision(self):
        self.setUpCatalog()
        plan = self.components.inspect(self.source)
        self.assertFalse(plan['rig']['changed'])
        self.assertEqual(plan['parts'][0]['extras'][0]['name'], EXTRA1)
        before_rig = self.components.get('rig', 'human')['revision']
        self.components.register(plan['token'], [], new_parts=[ROOT])
        part = self.components.get('part', ROOT)
        self.assertEqual(part['revision'], 1)
        self.assertEqual(json.loads(part['metadata_json'])['extras'][0]['name'], EXTRA1)
        self.assertIsNone(self.components.get('part', EXTRA1))
        self.assertEqual(before_rig, self.components.get('rig', 'human')['revision'])
        self.version['extra'] = 'v2'
        newer = self.components.inspect(self.source)
        self.assertFalse(newer['parts'][0]['content_unchanged'])
        self.components.register(newer['token'], [ROOT], new_parts=[])
        self.assertEqual(self.components.get('part', ROOT)['revision'], 2)

    def test_colors_validate_against_published_extras(self):
        self.setUpCatalog()
        plan = self.components.inspect(self.source)
        self.components.register(plan['token'], [], new_parts=[ROOT])
        with connect(self.components.db) as db:
            db.execute("UPDATE character_component_records SET model_asset_id='123456',published_revision=revision")
        chars = CharacterStore(self.root)
        armor = ArmorCatalog(self.components)
        armor.save_set(dict(id='starter', displayName='Starter', armorType='light', expectedRevision=0))
        assemblies = CharacterAssemblies(self.root, chars, self.components, armor)
        payload = dict(id='test_female', display_name='Test', rig_id='human', gender='female',
                       armor_set_id='starter', face_parts={'head': self.head_name, 'hair': ROOT},
                       face_atlases={}, hair_colors={'primary': '#5a321e', 'extra_01': '#d43b68'},
                       expected_revision=0)
        snap = assemblies.save(payload)
        resolved = snap['items'][0]['assembly_resolved']
        self.assertTrue(resolved['ready'], resolved['missing'])
        self.assertEqual(resolved['parts']['hair']['colors'],
                         {'primary': '#5A321E', 'extra_01': '#D43B68'})
        self.assertEqual(resolved['parts']['hair']['extras'], [EXTRA1])
        payload['id'] = 'bad_channels'
        payload['hair_colors'] = {'extra_02': '#FFFFFF'}
        with self.assertRaisesRegex(ValueError, 'channel'):
            assemblies.save(payload)
        payload['id'] = 'bad_hex'
        payload['hair_colors'] = {'extra_01': 'red'}
        with self.assertRaisesRegex(ValueError, '#RRGGBB'):
            assemblies.save(payload)

    def test_runtime_uses_one_model_pivot_and_whitelisted_meshes(self):
        builder = (self.root / 'src/server/character/CharacterAssemblyBuilder.luau') if hasattr(self, 'root') else Path(__file__).resolve().parents[2] / 'src/server/character/CharacterAssemblyBuilder.luau'
        code = builder.read_text()
        client = (Path(__file__).resolve().parents[2] / 'src/client/character/HairAttachmentController.luau').read_text()
        self.assertIn('rigidHairFromAsset(raw, part.id, part.extras or {})', code)
        self.assertIn('"unregistered hair MeshPart "', code)
        self.assertIn('group:PivotTo(delta * group:GetPivot())', code)
        self.assertIn('CharacterHairExtraWeld', code)
        self.assertIn('HairColorBinder.Apply(hairGroup, part.colors or {})', code)
        self.assertLess(code.index('CharacterAtlasBinder.Apply(mesh, part.atlas_image_id)'),
                        code.index('HairColorBinder.Apply(hairGroup, part.colors or {})'))
        self.assertIn('state.group:PivotTo(delta * state.group:GetPivot())', client)


if __name__ == '__main__':
    unittest.main()
