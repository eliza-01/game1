"""Rigid equipment contract; M607 supersedes the M336 frame follower."""
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[2]
def source(path): return (ROOT / path).read_text(encoding='utf-8')
class UnifiedBoneMountTests(unittest.TestCase):
    def test_no_runtime_follower(self):
        for path in ('src/client/character/HairAttachmentController.luau', 'src/client/weapon/WeaponAttachmentController.luau', 'src/client/character/BoneMountedAttachmentController.luau'):
            self.assertFalse((ROOT/path).exists())
        for path in (ROOT/'src').rglob('*.luau'):
            self.assertNotIn('BoneMountedAttachmentController', path.read_text(encoding='utf-8'))
    def test_same_mount_for_character_and_npc(self):
        mount=source('src/shared/rig/RigidEquipmentMount.luau')
        equip=source('src/server/weapon/WeaponEquipService.luau')
        builder=source('src/server/character/CharacterAssemblyBuilder.luau')
        for token in ('joint.Attachment0 = socket','joint.Attachment1 = jointGrip','grip.CFrame * offset:Inverse()', 'CFrame.Angles(math.rad(-90), 0, 0)', 'SocketFacing.FullFrame(CFrame.identity, true)'):
            self.assertIn(token,mount)
        self.assertEqual(mount.count('Instance.new("RigidConstraint")'),1)
        self.assertNotIn('RenderStepped',mount)
        self.assertIn('RigidMount.Attach(group, anchor, target, "hair")',builder)
        self.assertIn('RigidMount.Attach(weapon, grip, targetBone, "weapon")',equip)
        self.assertIn('RigidMount.Attach(weapon, grip, bone, "weapon")',equip)
        self.assertIn('WeaponEquipService.EquipVisual(',source('src/server/npc/NpcEquipmentService.luau'))
    def test_timeline_and_bow(self):
        timeline=source('system/studio-plugin/modules/StudioTimelinePreview.luau')
        self.assertIn('item:PivotTo(delta * item:GetPivot())',timeline)
        self.assertNotIn('RenderStepped:Connect',timeline)
        self.assertIn('RigidMount.GetBowReleaseOrigin(character)',source('src/client/combat/AttackController.luau'))
if __name__=='__main__': unittest.main()
