"""M328 rollback guard: damage must sample original equipped weapon geometry."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def source(path):
    return (ROOT / path).read_text(encoding="utf-8")


class PreviousWeaponPoseContract(unittest.TestCase):
    def test_pose_samples_equipped_weapon_not_local_clone(self):
        attack = source("src/client/combat/AttackController.luau")
        self.assertIn("WeaponAttackVolume.ReadEquippedWeaponBox(character)", attack)
        self.assertNotIn("WeaponAttachmentController.ReadEquippedWeaponBox(character)", attack)
        weapon = source("src/client/weapon/WeaponAttachmentController.luau")
        self.assertIn("weapon:PivotTo(", weapon)
        self.assertNotIn("RuntimeBoneVisual", weapon)

    def test_hair_uses_original_mount(self):
        hair = source("src/client/character/HairAttachmentController.luau")
        self.assertIn("state.group:PivotTo(", hair)
        self.assertNotIn("RuntimeBoneVisual", hair)

    def test_volume_debug_is_not_gameplay_and_only_updates_when_visible(self):
        debug = source("src/client/dev/TestLoadoutController.luau")
        self.assertIn("if volumeVisible then\n                renderWeaponHitVolume()", debug)
        self.assertIn("volumeConnection:Disconnect()", debug)
        self.assertEqual(debug.count("Instance.new(\"Part\")"), 3)


if __name__ == "__main__":
    unittest.main()
