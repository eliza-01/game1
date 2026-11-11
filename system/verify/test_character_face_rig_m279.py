"""M279 regressions: face overlay follows the actually published deform bones."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class TestPublishedFaceRig(unittest.TestCase):
    def test_presentation_uses_deform_face_bones(self):
        code = (ROOT / 'src/client/character/animation/FacePresentation.luau').read_text()
        contract = (ROOT / 'src/shared/character/FaceEmotionContract.luau').read_text()
        for name in ('face_eye_l','face_eye_r','face_brow_l','face_brow_r'):
            self.assertIn(name, code)
            self.assertIn(name, contract)
        for name in ('face_eye_ctrl_l','face_eye_ctrl_r','face_brow_ctrl_l','face_brow_ctrl_r'):
            self.assertNotIn('="'+name+'"', code)

    def test_active_female_rig_has_expected_deform_bones(self):
        manifest = json.loads((ROOT / 'assets/manifests/character-components.json').read_text())
        rig = next(item for item in manifest['items'] if item['kind']=='rig' and item['id']=='human_female')
        bones = {row['name'] for row in rig['metadata']['bones']}
        for name in ('face_eye_l','face_eye_r','face_brow_l','face_brow_r'):
            self.assertIn(name,bones)
        self.assertTrue(all(name not in bones for name in ('face_eye_ctrl_l','face_brow_ctrl_l')))

    def test_studio_smoke_fixtures_use_live_slot_contract(self):
        split = (ROOT / 'system/verify/studio_split_face_idle_smoke_m271.luau').read_text()
        events = (ROOT / 'system/verify/studio_face_events_regression.luau').read_text()
        self.assertIn('bone("face_eye_l"', split)
        self.assertIn('part:SetAttribute("CharacterPartSlot",slot)', events)
        self.assertIn('human_common_m001_eye_', events)
        self.assertNotIn('eyes_01_spiral', events)

    def test_old_animation_rig_cannot_silently_bind(self):
        source = (ROOT / 'src/client/character/animation/FaceAnimationController.luau').read_text()
        self.assertIn('tostring(target.asset_id)==tostring(asset)', source)
        self.assertIn('Re-register/re-export for the active rig', source)


if __name__ == '__main__':
    unittest.main()
