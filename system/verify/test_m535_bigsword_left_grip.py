"""The server chooses the hand once; existing client follows the same bone."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class BigswordGrip(unittest.TestCase):
    def test_player_primary_socket_policy(self):
        equip = (ROOT / 'src/server/weapon/WeaponEquipService.luau').read_text(encoding='utf8')
        self.assertIn('local kind = string.lower(weaponType)', equip)
        self.assertIn('return if kind == "bow" or kind == "bigsword" then LEFT_SOCKET_NAMES else RIGHT_SOCKET_NAMES', equip)
        self.assertIn('local targetBone = findCharacterBone(character, socketNames(tostring(row.weaponType or "")))', equip)
        self.assertIn('weapon:SetAttribute("WeaponTargetBoneName", targetBone.Name)', equip)
        self.assertIn('RigidMount.Attach(weapon, grip, targetBone, "weapon")', equip)

    def test_dual_and_npc_explicit_hand_preserved(self):
        equip = (ROOT / 'src/server/weapon/WeaponEquipService.luau').read_text(encoding='utf8')
        self.assertIn('local leftBone = if isDual then findCharacterBone(character, LEFT_SOCKET_NAMES) else nil', equip)
        self.assertIn('left:SetAttribute("WeaponTargetBoneName", leftBone.Name)', equip)
        self.assertIn('local names = if hand == "right" then RIGHT_SOCKET_NAMES else if hand == "left" then LEFT_SOCKET_NAMES else nil', equip)
        client = (ROOT / 'src/shared/rig/RigidEquipmentMount.luau').read_text(encoding='utf8')
        self.assertIn('joint.Attachment0 = socket', client)
        self.assertIn('joint.Attachment1 = jointGrip', client)
