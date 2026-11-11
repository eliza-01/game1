"""M196: a rejected neighbour cannot hide a valid rigid hairstyle.

The partial confirmation is a server-side contract, not just a UI checkbox.
"""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'control-center'))
from character_core.components import CharacterComponents, ComponentConflict
from character_core.part_names import parse_part
from sqlite_connection import connect
from test_character_rig_inspect_independent_m195 import IDENTITY


class PartialHairInspectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'human.fbx'
        self.source.write_bytes(b'fixture')
        self.bones = [dict(name='root', parent='', matrix=IDENTITY[:]),
                      dict(name='hair_mount', parent='root', matrix=IDENTITY[:])]
        self.info = dict(armature='human_armature', bones=self.bones, parts=[
            dict(name='human_common_m003_hair', armature='', skeleton=[], used_bones=[],
                 attachment='hair_mount', attachment_mode='pivot', vertices=4,
                 triangles=2, content_sha256='hair-content', materials=[]),
        ], part_errors=[dict(name='eyebrows_01_l', message='eyebrows_01_l: unsupported component name')])
        self.store = CharacterComponents(self.root, analyzer=self.analyze)

    def analyze(self, _root, _source, output=None):
        if output:
            output.mkdir(parents=True, exist_ok=True)
            (output / 'rig.fbx').write_bytes(b'rig')
            (output / 'human_common_m003_hair.fbx').write_bytes(b'hair')
        return copy.deepcopy(self.info)

    def test_inspect_keeps_hair_and_requires_explicit_partial_approval(self):
        plan = self.store.inspect(self.source)
        self.assertEqual([part['id'] for part in plan['parts']], ['human_common_m003_hair'])
        self.assertEqual(plan['parts'][0]['attachment_mode'], 'pivot')
        self.assertTrue(plan['partial_required'])
        self.assertFalse(plan['rig_only_required'])
        self.assertIn('eyebrows_01_l', plan['part_error'])
        with self.assertRaisesRegex(ComponentConflict, 'explicit approval'):
            self.store.register(plan['token'], [])
        self.assertEqual(self.store.snapshot()['items'], [])
        self.store.register(plan['token'], [], allow_partial=True)
        self.assertIsNotNone(self.store.get('part', 'human_common_m003_hair'))
        self.assertIsNone(self.store.get('part', 'eyebrows_01_l'))
        self.assertTrue((self.root / self.store.get('part', 'human_common_m003_hair')['prepared_path']).is_file())

    def test_changed_rig_can_still_be_replaced_with_rig_only_without_touching_parts(self):
        plan = self.store.inspect(self.source)
        self.store.register(plan['token'], [], allow_partial=True)
        before = self.store.get('part', 'human_common_m003_hair')
        self.info['bones'][0]['matrix'][3] = 1.0
        plan = self.store.inspect(self.source)
        self.assertTrue(plan['rig']['changed'])
        self.assertTrue(plan['partial_required'])
        self.store.register(plan['token'], [], replace_rig=True, rig_only=True)
        self.assertEqual(self.store.get('part', 'human_common_m003_hair'), before)
        self.assertEqual(self.store.get('rig', 'human')['revision'], 2)
        with connect(self.store.db) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM character_component_history WHERE kind='part'").fetchone()[0], 0)

    def test_rejects_mutated_source_and_changed_extraction_results(self):
        plan = self.store.inspect(self.source)
        # The original path may change, but the frozen snapshot must not.
        self.source.write_bytes(b'another file')
        self.info['parts'][0]['content_sha256'] = 'changed'
        with self.assertRaisesRegex(ComponentConflict, 'FBX changed during extraction'):
            self.store.register(plan['token'], [], allow_partial=True)
        self.assertEqual(self.store.snapshot()['items'], [])

    def test_invalid_only_is_not_partially_registerable(self):
        self.info['parts'] = []
        with self.assertRaisesRegex(ValueError, 'eyebrows_01_l'):
            self.store.inspect(self.source)
        self.assertEqual(self.store.snapshot()['items'], [])

    def test_no_broadening_of_eyebrow_naming(self):
        with self.assertRaises(ValueError):
            parse_part('eyebrows_01_l')
        self.assertEqual(parse_part('human_common_m003_hair')['slot'], 'hair')

    def test_blender_adapter_scans_valid_hair_even_when_bad_eyebrow_precedes_it(self):
        from test_character_rigid_hair_m194 import FakeMesh, HairImportTests
        adapter, bpy, rig, hair = HairImportTests().load_adapter()
        bpy.context.scene.objects = [rig, FakeMesh('eyebrows_01_l'), hair]
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / 'report.json'
            adapter.main(Path(directory) / 'source.fbx', report)
            info = json.loads(report.read_text())
        self.assertEqual([part['name'] for part in info['parts']], ['human_common_m003_hair'])
        self.assertEqual(info['parts'][0]['attachment_mode'], 'pivot')
        self.assertEqual(info['part_errors'][0]['name'], 'eyebrows_01_l')

    def test_ui_has_server_confirmed_partial_flow(self):
        js = (Path(__file__).resolve().parents[1] / 'control-center/static/character-components.js').read_text()
        self.assertIn('plan.partial_required', js)
        self.assertIn('check.dataset.partialApproval', js)
        self.assertIn('allowPartial:approval.allowPartial', js)
        api = (Path(__file__).resolve().parents[1] / 'control-center/api/character_components.py').read_text()
        self.assertIn("allow_partial=payload.get('allowPartial',False)", api)


if __name__ == '__main__':
    unittest.main()
