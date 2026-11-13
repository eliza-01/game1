"""M280: authored Bone socket facing; independent solid eye/brow colors."""
import unittest
from pathlib import Path

from test_character_armor_v2_m269 import ArmorV2Tests

ROOT = Path(__file__).resolve().parents[2]
SOLID = ('eye_l', 'eye_r', 'eyebrow_l', 'eyebrow_r')

class CharacterColorSocketTests(unittest.TestCase):
    def fixture(self):
        fixture = ArmorV2Tests('test_geometry_identity_not_equipment_set')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.register_set('starter', ())
        return fixture

    def payload(self):
        return dict(id='test_colors',display_name='Colors',gender='male',rig_id='human',
            armor_set_id='starter',expected_revision=0,
            face_parts=dict(head='human_male_m001_head',eye_l='human_male_m001_eye_l',
                            eye_r='human_male_m001_eye_r',eyebrow_l='human_male_m001_eyebrow_l',
                            eyebrow_r='human_male_m001_eyebrow_r'),
            face_colors=dict(eye_l='#112233',eye_r='#abcdef',eyebrow_l='#AB12CD',eyebrow_r='#000000'),
            face_atlases={})

    def test_face_colors_saved_and_resolved_without_appearance(self):
        fixture=self.fixture()
        row=fixture.assemblies.save(self.payload())['items'][0]
        self.assertTrue(row['assembly_resolved']['ready'], row['assembly_resolved']['missing'])
        self.assertEqual(row['assembly']['face_colors']['eye_r'],'#ABCDEF')
        for slot in SOLID:
            resolved=row['assembly_resolved']['parts'][slot]
            self.assertEqual(resolved['color'],row['assembly']['face_colors'][slot])
            self.assertEqual(resolved['atlas_image_id'],'')
            self.assertEqual(resolved['appearance_id'],'')

    def test_atlas_on_solid_face_rejected_without_side_effects(self):
        fixture=self.fixture()
        p=self.payload();p['face_atlases']={'eye_l':'123'}
        with self.assertRaisesRegex(ValueError,'atlases are available only'):
            fixture.assemblies.save(p)
        self.assertIsNone(fixture.characters.get('test_colors'))

    def test_invalid_or_dangling_face_color_rejected(self):
        fixture=self.fixture()
        for color in ('red','#12345','#GG00FF',None):
            p=self.payload();p['face_colors']['eye_l']=color
            with self.subTest(color=color),self.assertRaisesRegex(ValueError,'color must'):
                fixture.assemblies.save(p)
        p=self.payload();del p['face_parts']['eye_l']
        with self.assertRaisesRegex(ValueError,'choose a MeshPart'):
            fixture.assemblies.save(p)
        p=self.payload();p['face_colors']['head']='#FFFFFF'
        with self.assertRaisesRegex(ValueError,'only eyes and eyebrows'):
            fixture.assemblies.save(p)

    def test_previous_face_atlas_does_not_affect_new_solid_tint_resolution(self):
        fixture=self.fixture()
        fixture.assemblies.save(self.payload())
        recipe=fixture.characters.get('test_colors')['assembly']
        # Previously stored eye appearance is obsolete: no atlas is resolved for solid eyes.
        recipe['face_parts']['eye_l']['appearanceId']='retired-eye-appearance'
        resolved=fixture.assemblies.resolve(recipe)
        self.assertTrue(resolved['ready'], resolved['missing'])
        self.assertEqual(resolved['parts']['eye_l']['atlas_image_id'],'')
        self.assertEqual(resolved['parts']['eye_l']['color'],'#112233')

    def test_shared_facing_and_same_hair_alignment_on_server_and_client(self):
        shared=(ROOT/'src/shared/world/SocketFacing.luau').read_text()
        self.assertIn('if fromBone then -frame.UpVector else frame.LookVector',shared)
        self.assertIn('CFrame.lookAlong(frame.Position, SocketFacing.Forward(frame, true), frame.LookVector)',shared)
        source=(ROOT/'src/shared/rig/BoneModelMount.luau').read_text()
        self.assertIn('SocketFacing.FullFrame(frame, true)',source)
        for name in ('src/server/character/CharacterAssemblyBuilder.luau',
                     'src/client/character/BoneMountedAttachmentController.luau'):
            source=(ROOT/name).read_text()
            self.assertIn('BoneModelMount.SocketFrame(',source)
        spawn=(ROOT/'src/shared/world/HouseSpawnOrientation.luau').read_text()
        self.assertIn('SocketFacing.Forward(socketFrame, fromBone)',spawn)
        effects=(ROOT/'src/server/world/HouseSocketEffects.luau').read_text()
        self.assertIn('SocketFacing.FullFrame(authoredFrame, isBone)',effects)

    def test_tint_is_shared_between_hair_and_face_and_face_ui_has_no_atlas(self):
        builder=(ROOT/'src/server/character/CharacterAssemblyBuilder.luau').read_text()
        hair=(ROOT/'src/server/character/HairColorBinder.luau').read_text()
        ui=(ROOT/'system/control-center/static/character-assemblies.js').read_text()
        self.assertIn('CharacterColorBinder.Apply(mesh, part.color)',builder)
        self.assertIn('CharacterColorBinder.Apply(mesh, hex)',hair)
        self.assertIn("const atlasSlots=['head','hair'];",ui)
        self.assertIn("const solidFaceSlots=['eye_l','eye_r','eyebrow_l','eyebrow_r'];",ui)
        self.assertIn('face_colors:Object.fromEntries(solidFaceSlots',ui)

if __name__=='__main__':
    unittest.main()
