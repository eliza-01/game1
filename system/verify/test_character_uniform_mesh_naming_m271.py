"""M271: single character MeshPart grammar and independent face components."""
import copy
import sys
import tempfile
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'control-center'))
from character_core.part_names import parse_part, rigid_pivot_mount_for_part, default_allowed_genders
from character_core.components import CharacterComponents

IDENTITY=[1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.]

class NamingTests(unittest.TestCase):
    def test_all_geometry_has_one_family_grammar(self):
        examples={
            'human_male_m001_head':('head','human_male_m001','male'),
            'human_male_m001_eye_l':('eye_l','human_male_m001','male'),
            'human_male_m001_eyebrow_r':('eyebrow_r','human_male_m001','male'),
            'human_female_m001_hair':('hair','human_female_m001','female'),
            'human_common_m002_eye_r':('eye_r','human_common_m002','common'),
            'human_male_m002_lower':('lower','human_male_m002','male'),
        }
        for name,(slot,family,gender) in examples.items():
            with self.subTest(name=name):
                meta=parse_part(name)
                self.assertEqual((meta['slot'],meta['mesh_family_id'],meta['gender']), (slot,family,gender))
                self.assertEqual(meta['rig_profile_id'],'human')
                self.assertEqual(meta['set_id'],'')
                self.assertEqual(meta['role'],'part')
                self.assertEqual(default_allowed_genders(meta),['male','female'] if gender=='common' else [gender])
        self.assertEqual(rigid_pivot_mount_for_part('human_female_m001_hair'),'hair_mount')
        self.assertEqual(rigid_pivot_mount_for_part('human_male_m001_eye_l'),'')
        effect=parse_part('human_male_m001_eye_l_spiral')
        self.assertEqual((effect['slot'],effect['role']),('eye_l','effect'))

    def test_no_old_or_ambiguous_component_names(self):
        for name in ('head_01_male','eyes_01','eyes_01_l','eyebrows_01','hair_03_common',
                     'newborn_upper','human_male_m000_head','human_male_m001_eyebrows',
                     'human_female_m001_eyebrow_r_spiral','human_male_m001_eye',
                     'human_male_m001_eye_l.001','Human_Male_m001_eye_r'):
            with self.subTest(name=name),self.assertRaises(ValueError):parse_part(name)

    def test_inspect_preserves_separate_face_parts_and_rejects_wrong_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=root/'test.fbx';source.write_bytes(b'fixture')
            names=['human_male_m001_eye_l','human_male_m001_eye_r',
                   'human_male_m001_eyebrow_l','human_male_m001_eyebrow_r']
            bad=None
            def analyzer(_root,_source,_out=None):
                rig=[dict(name='root',parent='',matrix=copy.deepcopy(IDENTITY))]
                return dict(armature='human_armature',bones=rig,parts=[dict(name=n,
                    armature='human_armature',vertices=3,triangles=1,content_sha256=n,
                    skeleton=rig,used_bones=['root']) for n in (names if bad is None else [bad])])
            catalog=CharacterComponents(root,analyzer=analyzer)
            inspected=catalog.inspect(source)
            self.assertEqual([r['slot'] for r in inspected['parts']],
                ['eye_l','eye_r','eyebrow_l','eyebrow_r'])
            self.assertEqual(len(inspected['parts']),4)
            self.assertTrue(all(r['mesh_family_id']=='human_male_m001' for r in inspected['parts']))
            bad='elf_male_m001_eye_l'
            with self.assertRaisesRegex(ValueError,'mesh family and gender must match'):
                catalog.inspect(source)

if __name__=='__main__':unittest.main()
