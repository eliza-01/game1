"""M465: common geometry is compatible by published deforming bind chain.

An irrelevant face/weapon bone difference must not hide otherwise compatible
male eyes, but a used bone or any of its ancestors must be identical.
"""
import copy
import json
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'control-center'))
from character_core.part_names import part_bind_matches, required_bind_bones
from character_core.components import CharacterComponents


def bone(name, parent='', x=0):
    return dict(name=name, parent=parent,
                matrix=[1., 0., 0., x, 0., 1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1.])


FEMALE = [bone('root'), bone('head', 'root'), bone('face_eye_l', 'head', 1),
          bone('face_eye_r', 'head', 2), bone('hand_l', 'root'),
          bone('weapon_grip_l', 'hand_l', 5)]
MALE = copy.deepcopy(FEMALE)
MALE[-1]['matrix'][3] = 50.  # Different non-deforming weapon grip.


class CommonBindChainsM465(unittest.TestCase):
    def test_irrelevant_socket_difference_does_not_hide_common_eyes(self):
        part = copy.deepcopy(FEMALE)
        self.assertEqual(required_bind_bones(part, ['face_eye_l']), {'root', 'head', 'face_eye_l'})
        self.assertTrue(part_bind_matches(FEMALE, MALE, part, used_bones=['face_eye_l']))
        self.assertTrue(part_bind_matches(FEMALE, MALE, part, used_bones=['face_eye_r']))

    def test_used_or_ancestor_bind_mismatch_rejected(self):
        for changed in ('head', 'face_eye_l'):
            with self.subTest(changed=changed):
                male = copy.deepcopy(MALE)
                next(row for row in male if row['name'] == changed)['matrix'][3] += .1
                with self.assertRaisesRegex(ValueError, 'incompatible bind'):
                    part_bind_matches(FEMALE, male, FEMALE, used_bones=['face_eye_l'])

    def test_published_mesh_bind_mismatch_and_missing_ancestor_rejected(self):
        mismatch = copy.deepcopy(FEMALE)
        mismatch[2]['matrix'][3] += .2
        with self.assertRaisesRegex(ValueError, 'incompatible bind'):
            part_bind_matches(FEMALE, MALE, mismatch, used_bones=['face_eye_l'])
        with self.assertRaisesRegex(ValueError, 'missing bind bone'):
            part_bind_matches(FEMALE, MALE, FEMALE, used_bones=['missing_eye'])
        with self.assertRaisesRegex(ValueError, 'no bone influences'):
            part_bind_matches(FEMALE, MALE, FEMALE, used_bones=[])

    def test_cross_rig_resolver_checks_part_publication_and_gender(self):
        store = object.__new__(CharacterComponents)
        components = {
            ('rig', 'human_female'): dict(id='human_female', metadata_json=json.dumps({'bones': FEMALE})),
            ('rig', 'human_male'): dict(id='human_male', metadata_json=json.dumps({'bones': MALE})),
        }
        store.get = lambda kind, key: components.get((kind, key))
        store.publication_metadata = lambda row: json.loads(row['metadata_json'])
        common = dict(id='human_common_m001_eye_l', rig_id='human_female', gender='common',
                      metadata_json=json.dumps({'skeleton': FEMALE, 'used_bones': ['face_eye_l']}))
        self.assertTrue(store.part_compatible_with_rig(common, 'human_male'))
        self.assertTrue(store.part_compatible_with_rig(common, 'human_female'))
        self.assertFalse(store.part_compatible_with_rig({**common, 'gender': 'female'}, 'human_male'))
        changed = copy.deepcopy(FEMALE)
        next(b for b in changed if b['name'] == 'face_eye_l')['matrix'][3] += .25
        self.assertFalse(store.part_compatible_with_rig({**common, 'metadata_json':json.dumps({
            'skeleton': changed, 'used_bones': ['face_eye_l']})}, 'human_male'))

    def test_runtime_verifies_only_weighted_ancestor_chain(self):
        runtime = (Path(__file__).resolve().parents[2] /
                   'src/server/character/CharacterAssemblyBuilder.luau').read_text(encoding='utf8')
        self.assertIn('for name in required do', runtime)
        self.assertIn('for _, name in part.used_bones do', runtime)
        self.assertIn('"incompatible bind for " .. name', runtime)
        self.assertIn('SkinConnection.Connect', runtime)


if __name__ == '__main__':
    unittest.main()
