"""M114: strict house identity, advisory features and native UI sizing."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from real_estate.contracts import validate_analysis, warnings_for_analysis
from test_real_estate_m107 import skeleton


def copy(value):
    return json.loads(json.dumps(value))


class HouseAuthoringContract(unittest.TestCase):
    def test_only_house_and_named_house_armature_are_required(self):
        source = skeleton()
        for part in source['meshes']:
            part['bones'] = []
            part['influencedBones'] = []
        self.assertIs(validate_analysis(source), source)
        without_door = {'meshes': [source['meshes'][0]]}
        self.assertIs(validate_analysis(without_door), without_door)
        self.assertEqual({w['code'] for w in warnings_for_analysis(without_door)},
                         {'missing_door', 'missing_chimney_bone'})
        for wrong in ('', 'another_armature', None):
            modified = copy(without_door)
            modified['meshes'][0]['armature'] = wrong
            with self.subTest(armature=wrong), self.assertRaisesRegex(ValueError, 'house_armature'):
                validate_analysis(modified)
        for no_house in ({'meshes': []}, {'meshes': [source['meshes'][1]]}):
            with self.assertRaisesRegex(ValueError, 'house'):
                validate_analysis(no_house)
            self.assertIn('missing_house', {w['code'] for w in warnings_for_analysis(no_house)})

    def test_door_states_and_chimney_bone_produce_specific_advisories(self):
        base = skeleton()
        self.assertEqual(warnings_for_analysis(base), [])
        without_door = copy(base)
        without_door['meshes'].pop()
        self.assertEqual([w['code'] for w in warnings_for_analysis(without_door)], ['missing_door'])
        bare_door = copy(base)
        bare_door['meshes'][1].update(armature='', bones=[])
        self.assertEqual([w['code'] for w in warnings_for_analysis(bare_door)],
                         ['missing_door_armature'])
        bare_rig = copy(base)
        bare_rig['meshes'][1]['bones'] = []
        self.assertEqual([w['code'] for w in warnings_for_analysis(bare_rig)],
                         ['missing_door_bone'])
        no_chimney = copy(base)
        no_chimney['meshes'][0]['bones'] = []
        self.assertEqual([w['code'] for w in warnings_for_analysis(no_chimney)],
                         ['missing_chimney_bone'])
        other_bone = copy(base)
        other_bone['meshes'][0]['bones'] = [{'name':'arbitrary_bone'}]
        self.assertEqual([w['code'] for w in warnings_for_analysis(other_bone)],
                         ['missing_chimney_bone'])
        unassigned = copy(base)
        unassigned['unassignedArmatures'] = ['UnusedRig']
        self.assertIn('unassigned_armature',
                      {w['code'] for w in warnings_for_analysis(unassigned)})
        self.assertIs(validate_analysis(unassigned), unassigned)
        with self.subTest('optional extra mesh without armature'):
            other = copy(base)
            other['meshes'].append({'name':'stairs', 'armature':'', 'vertices':9, 'bones':[]})
            validate_analysis(other)
            self.assertEqual(warnings_for_analysis(other), [])

    def test_authoring_blender_sync_and_layout_have_separate_responsibilities(self):
        analyze = (ROOT/'system/asset-manager/analyze_real_estate_fbx.py').read_text('utf-8')
        prepare = (ROOT/'system/asset-manager/prepare_real_estate_publication_fbx.py').read_text('utf-8')
        studio = (ROOT/'system/studio-plugin/modules/StudioRealEstateModel.luau').read_text('utf-8')
        js = (ROOT/'system/control-center/static/real-estate.js').read_text('utf-8')
        css = (ROOT/'system/control-center/static/real-estate.css').read_text('utf-8')
        shell = (ROOT/'system/control-center/static/asset-manager.css').read_text('utf-8')
        for text in (analyze,prepare):
            self.assertIn("rig.name.casefold() != 'house_armature'",text)
        self.assertIn('rigWarnings = rigWarnings',studio)
        self.assertIn('return findMesh(root, part), count, warnings',studio)
        self.assertNotIn('error(part .. " rig lost bone',studio)
        self.assertIn('Studio import warnings',js)
        self.assertIn('white-space:nowrap; flex:0 0 auto',css)
        self.assertIn('width:max-content; max-width:100%',css)
        self.assertIn('main{display:grid;grid-template-columns:300px minmax(0,1fr);gap:18px;margin:auto}',shell)


if __name__ == '__main__':
    unittest.main()
