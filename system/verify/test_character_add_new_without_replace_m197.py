"""M197 regression: add new parts from a mixed FBX without touching any registered parts."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'control-center'))
from character_core.components import CharacterComponents, ComponentConflict
from sqlite_connection import connect

IDENTITY = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
OLD_PARTS = ['head_01_male', 'newborn_boots', 'newborn_gloves', 'newborn_lower', 'newborn_upper']


class AddNewWithoutReplaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'human.fbx'
        self.source.write_bytes(b'fbx')
        self.bones = [dict(name='root', parent='', matrix=IDENTITY[:]),
                      dict(name='hair_mount', parent='root', matrix=IDENTITY[:])]
        self.info = dict(armature='human_armature', bones=self.bones, parts=[
            self.skinned(name) for name in OLD_PARTS
        ])
        self.store = CharacterComponents(self.root, analyzer=self.analyze)
        initial = self.store.inspect(self.source)
        self.store.register(initial['token'], [])
        with connect(self.store.db) as db:
            for name in OLD_PARTS:
                db.execute("UPDATE character_component_records SET model_asset_id=?, published_revision=revision "
                           "WHERE kind='part' AND id=?", ('published_' + name, name))
        self.old = {name: self.store.get('part', name) for name in OLD_PARTS}
        self.info['parts'].append(self.rigid_hair())

    def skinned(self, name):
        return dict(name=name, vertices=3, triangles=1, content_sha256='old-'+name,
                    armature='human_armature', skeleton=copy.deepcopy(self.bones), used_bones=['root'])

    def rigid_hair(self, name='hair_03_common'):
        return dict(name=name, vertices=10, triangles=18, content_sha256='rigid-'+name,
                    armature='', skeleton=[], used_bones=[], attachment='hair_mount',
                    attachment_mode='pivot', materials=[])

    def analyze(self, _root, _source, output=None):
        if output:
            output = Path(output)
            output.mkdir(parents=True, exist_ok=True)
            for name in ('rig', *(p['name'] for p in self.info['parts'])):
                (output / (name + '.fbx')).write_bytes(name.encode())
        return copy.deepcopy(self.info)

    def test_hair_only_registration_does_not_touch_five_published_components(self):
        plan = self.store.inspect(self.source)
        self.assertEqual(len(plan['conflicts']), 5)
        self.assertEqual(len(plan['registered']), 5)
        self.assertEqual([p['id'] for p in plan['parts'] if not p['existing_revision']], ['hair_03_common'])
        result = self.store.register(plan['token'], [], new_parts=['hair_03_common'])
        self.assertIsNotNone(self.store.get('part', 'hair_03_common'))
        self.assertEqual(self.store.get('part', 'hair_03_common')['revision'], 1)
        self.assertEqual(self.store.get('part', 'hair_03_common')['model_asset_id'], '')
        for name in OLD_PARTS:
            self.assertEqual(self.store.get('part', name), self.old[name], name)
        with connect(self.store.db) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM character_component_history WHERE kind='part'").fetchone()[0], 0)
        self.assertEqual(len(result['items']), 7)  # one rig, five old parts, new hair
        # The new component appears immediately in the normal publication catalog.
        self.assertTrue(any(r['id'] == 'hair_03_common' and r['status'] == 'registered' for r in result['items']))

    def test_legacy_client_omitting_new_parts_adds_only_new_by_default(self):
        plan = self.store.inspect(self.source)
        self.store.register(plan['token'], [])
        self.assertIsNotNone(self.store.get('part', 'hair_03_common'))
        for name in OLD_PARTS:
            self.assertEqual(self.store.get('part', name), self.old[name])

    def test_unselected_registered_but_unpublished_part_is_preserved(self):
        with connect(self.store.db) as db:
            db.execute("UPDATE character_component_records SET model_asset_id='',published_revision=0 "
                       "WHERE kind='part' AND id='newborn_lower'")
        old_unpublished = self.store.get('part', 'newborn_lower')
        plan = self.store.inspect(self.source)
        self.assertEqual(len(plan['registered']), 5)
        self.assertEqual(len(plan['conflicts']), 4)
        self.store.register(plan['token'], [], new_parts=['hair_03_common'])
        self.assertEqual(self.store.get('part', 'newborn_lower'), old_unpublished)

    def test_only_one_explicit_replacement_changes_and_can_skip_new_hair(self):
        plan = self.store.inspect(self.source)
        self.store.register(plan['token'], ['newborn_upper'], new_parts=[])
        self.assertEqual(self.store.get('part', 'newborn_upper')['revision'], 2)
        self.assertEqual(self.store.get('part', 'newborn_upper')['model_asset_id'], 'published_newborn_upper')
        self.assertEqual(self.store.get('part', 'newborn_upper')['published_revision'], 1)
        self.assertIsNone(self.store.get('part', 'hair_03_common'))
        for name in OLD_PARTS:
            if name != 'newborn_upper':
                self.assertEqual(self.store.get('part', name), self.old[name])

    def test_invalid_selection_and_empty_operation_are_rejected(self):
        for replacements, new_parts, match in [
            (['hair_03_common'], [], 'replacement approval'),
            ([], ['newborn_upper'], 'new component selection'),
            ([], ['hair_03_common', 'hair_03_common'], 'new component selection'),
            (['newborn_upper', 'newborn_upper'], ['hair_03_common'], 'replacement approval'),
            ([], [], 'nothing selected'),
        ]:
            plan = self.store.inspect(self.source)
            with self.assertRaisesRegex(ComponentConflict, match):
                self.store.register(plan['token'], replacements, new_parts=new_parts)
            self.assertIsNone(self.store.get('part', 'hair_03_common'))
            for name in OLD_PARTS:
                self.assertEqual(self.store.get('part', name), self.old[name])

    def test_race_in_unselected_published_part_still_requires_reinspect(self):
        plan = self.store.inspect(self.source)
        with connect(self.store.db) as db:
            db.execute("UPDATE character_component_records SET model_asset_id='another' "
                       "WHERE kind='part' AND id='newborn_upper'")
        with self.assertRaisesRegex(ComponentConflict, 'published after inspection'):
            self.store.register(plan['token'], [], new_parts=['hair_03_common'])
        self.assertIsNone(self.store.get('part', 'hair_03_common'))

    def test_m196_partial_inspection_approval_remains_required(self):
        self.info['part_errors'] = [dict(name='eyebrows_01_l', message='eyebrows_01_l: invalid')]
        plan = self.store.inspect(self.source)
        self.assertTrue(plan['partial_required'])
        with self.assertRaisesRegex(ComponentConflict, 'explicit approval'):
            self.store.register(plan['token'], [], new_parts=['hair_03_common'])
        self.store.register(plan['token'], [], new_parts=['hair_03_common'], allow_partial=True)
        self.assertIsNotNone(self.store.get('part', 'hair_03_common'))
        self.assertIsNone(self.store.get('part', 'eyebrows_01_l'))


if __name__ == '__main__':
    unittest.main()
