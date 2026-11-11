"""M195: invalid FBX parts may not hide a changed primary rig."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'control-center'))
from character_core.components import CharacterComponents, ComponentConflict
from sqlite_connection import connect

IDENTITY = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]


class RigIndependentInspectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'human.fbx'
        self.source.write_bytes(b'source fixture')
        self.info = dict(
            armature='human_armature',
            bones=[dict(name='root', parent='', matrix=IDENTITY[:])],
            parts=[dict(name='human_male_m001_head', vertices=3, triangles=1,
                        content_sha256='headhash', armature='human_armature',
                        skeleton=[dict(name='root', parent='', matrix=IDENTITY[:])],
                        used_bones=['root'])],
        )
        self.fail_full = None
        self.rig_calls = []
        self.store = CharacterComponents(
            self.root, analyzer=self.full_analyzer, rig_analyzer=self.rig_analyzer,
        )

    def full_analyzer(self, root, source, output=None):
        if self.fail_full:
            raise ValueError(self.fail_full)
        if output:
            out = Path(output)
            out.mkdir(parents=True, exist_ok=True)
            for name in ('rig', *(part['name'] for part in self.info['parts'])):
                (out / (name + '.fbx')).write_bytes(name.encode())
        return copy.deepcopy(self.info)

    def rig_analyzer(self, root, source, output=None):
        self.rig_calls.append(bool(output))
        if output:
            out = Path(output)
            out.mkdir(parents=True, exist_ok=True)
            (out / 'rig.fbx').write_bytes(b'rig only')
        return dict(armature=self.info['armature'], bones=copy.deepcopy(self.info['bones']), parts=[])

    def initial_registration(self):
        plan = self.store.inspect(self.source)
        self.assertFalse(plan['rig_only_required'])
        self.store.register(plan['token'], [])
        with connect(self.store.db) as db:
            for kind, key in [('rig', 'human'), ('part', 'human_male_m001_head')]:
                db.execute("UPDATE character_component_records SET model_asset_id='12345', "
                           'published_revision=revision WHERE kind=? AND id=?', (kind, key))
        return self.store.get('part', 'human_male_m001_head')

    def change_rig(self):
        self.info['bones'][0]['matrix'][3] = 2.0

    def test_invalid_part_name_retains_replace_rig_and_forces_rig_only(self):
        before = self.initial_registration()
        self.change_rig()
        self.info['parts'][0]['name'] = 'eyebrows_01_l'  # intentionally unsupported
        plan = self.store.inspect(self.source)
        self.assertTrue(plan['rig']['changed'])
        self.assertTrue(plan['rig_only_required'])
        self.assertIn('eyebrows_01_l', plan['part_error'])
        self.assertEqual(plan['parts'], [])
        self.assertEqual(plan['conflicts'], [])
        with self.assertRaisesRegex(ComponentConflict, 'rig-only'):
            self.store.register(plan['token'], [], replace_rig=True, rig_only=False)
        result = self.store.register(plan['token'], [], replace_rig=True, rig_only=True)
        self.assertEqual(self.rig_calls, [True])
        self.assertEqual(self.store.get('rig', 'human')['revision'], 2)
        self.assertEqual(self.store.get('rig', 'human')['published_revision'], 1)
        self.assertEqual(self.store.get('rig', 'human')['model_asset_id'], '12345')
        self.assertEqual(self.store.get('part', 'human_male_m001_head'), before)
        self.assertEqual(len(result['items']), 2)
        with connect(self.store.db) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM character_component_history WHERE kind='part'").fetchone()[0], 0)

    def test_blender_full_inspect_failure_still_allows_changed_rig(self):
        self.initial_registration()
        self.change_rig()
        self.fail_full = 'eyebrows_01_l: one Armature modifier is required'
        plan = self.store.inspect(self.source)
        self.assertTrue(plan['rig_only_required'])
        self.assertTrue(plan['rig']['changed'])
        self.assertIn('Armature modifier', plan['part_error'])
        self.assertEqual(self.rig_calls, [False])
        self.store.register(plan['token'], [], replace_rig=True, rig_only=True)
        self.assertEqual(self.rig_calls, [False, True])

    def test_invalid_parts_do_not_suppress_errors_when_rig_unchanged(self):
        self.initial_registration()
        self.info['parts'][0]['name'] = 'eyebrows_01_l'
        with self.assertRaisesRegex(ValueError, 'eyebrows_01_l'):
            self.store.inspect(self.source)
        self.fail_full = 'bad skin weights'
        with self.assertRaisesRegex(ValueError, 'bad skin weights'):
            self.store.inspect(self.source)
        self.assertEqual(self.store.get('rig', 'human')['revision'], 1)

    def test_no_unregistered_rig_can_be_created_through_invalid_parts(self):
        self.info['parts'][0]['name'] = 'eyebrows_01_l'
        with self.assertRaisesRegex(ValueError, 'eyebrows_01_l'):
            self.store.inspect(self.source)
        self.assertIsNone(self.store.get('rig', 'human'))

    def test_valid_parts_keep_original_full_registration(self):
        self.initial_registration()
        self.change_rig()
        plan = self.store.inspect(self.source)
        self.assertFalse(plan['rig_only_required'])
        self.assertEqual(plan['parts'][0]['id'], 'human_male_m001_head')
        self.assertEqual(self.rig_calls, [])
        self.store.register(plan['token'], ['human_male_m001_head'], replace_rig=True)
        self.assertEqual(self.rig_calls, [])
        self.assertEqual(self.store.get('part', 'human_male_m001_head')['revision'], 2)


class RigBlenderAdapterTests(unittest.TestCase):
    def test_rig_only_does_not_validate_unrelated_mesh(self):
        from test_character_rigid_hair_m194 import FakeMesh, HairImportTests
        adapter, _bpy, _rig, _mesh = HairImportTests().load_adapter(FakeMesh('eyebrows_01_l'))
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / 'rig.json'
            adapter.main(Path(folder) / 'source.fbx', report, rig_only=True)
            data = json.loads(report.read_text())
        self.assertEqual(data['armature'], 'human_armature')
        self.assertEqual(data['parts'], [])
        self.assertEqual([b['name'] for b in data['bones']], ['hair_mount', 'root'])


if __name__ == '__main__':
    unittest.main()
