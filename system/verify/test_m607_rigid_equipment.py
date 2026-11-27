"""Structural regressions; engine behaviour must be accepted in Studio/DEV."""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def read(p): return (ROOT/p).read_text(encoding='utf-8')
class RigidEquipment(unittest.TestCase):
    def test_native_mount_is_one_shot_and_massless(self):
        s=read('src/shared/rig/RigidEquipmentMount.luau')
        for token in ('object.Anchored = false','object.CanCollide = false','object.CanTouch = false','object.CanQuery = false','object.Massless = true','object.RootPriority = -127','joint.Attachment0 = socket','joint.Attachment1 = jointGrip','StaticMount.Place(model, grip, Mount.SocketFrame(target, kind))','grip.CFrame * offset:Inverse()'):
            self.assertIn(token,s)
        self.assertEqual(s.count('Instance.new("RigidConstraint")'),1)
        for token in ('RunService','RenderStepped','Heartbeat','task.spawn',':Connect('): self.assertNotIn(token,s)
    def test_player_npc_dual_share_mount_and_clone_before_joint(self):
        s=read('src/server/weapon/WeaponEquipService.luau')
        self.assertLess(s.index('local left = weapon:Clone()'),s.index('RigidMount.Attach(weapon, grip, targetBone, "weapon")'))
        self.assertIn('RigidMount.Attach(left, leftGrip, leftBone, "weapon")',s)
        self.assertIn('RigidMount.Attach(weapon, grip, bone, "weapon")',s)
        self.assertIn('WeaponEquipService.EquipVisual(',read('src/server/npc/NpcEquipmentService.luau'))
    def test_compound_preview_and_readiness(self):
        s=read('src/shared/rig/RigidEquipmentMount.luau')
        self.assertLess(s.index('StaticMount.Place('),s.index('Instance.new("WeldConstraint")'))
        self.assertIn('weld.Part0 ~= root or weld.Part1 ~= part',s)
        self.assertIn('joint.Attachment0 ~= socket or joint.Attachment1 ~= grip',s)
        preview=read('src/client/character/CharacterCreationPreviewController.luau')
        self.assertIn('object.Anchored = not Mounts.IsEquipmentPart(object)',preview)
        self.assertIn('RunService.PostSimulation:Wait()',preview)
        self.assertIn('if not Mounts.HairAssemblyReady(instance) then',preview)
    def test_editor_is_not_runtime_dependency(self):
        self.assertFalse((ROOT/'src/client/character/BoneMountedAttachmentController.luau').exists())
        self.assertNotIn('BoneMountedAttachmentController',read('src/client/init.client.luau'))
        s=read('system/studio-plugin/modules/StudioTimelinePreview.luau')
        self.assertIn('frame * grip.WorldCFrame:Inverse()',s)
        self.assertNotIn('RenderStepped:Connect',s)
    def test_studio_stand_releases_only_equipment(self):
        s=read('src/server/testbed/CharacterTestStandPlayback.luau')
        self.assertIn('object:IsA("BasePart") and RigidMount.IsEquipmentPart(object)',s)
        self.assertIn('object.Anchored = false',s)
    def test_bow_uses_bone_and_local_geometry(self):
        s=read('src/shared/rig/RigidEquipmentMount.luau')
        self.assertIn('endpointFrame(socket) * grip.WorldCFrame:Inverse()',s)
        self.assertIn('delta:PointToWorldSpace(node.WorldPosition)',s)
        self.assertIn('RigidMount.GetBowReleaseOrigin(character)',read('src/client/combat/AttackController.luau'))
if __name__=='__main__': unittest.main()
