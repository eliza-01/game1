"""M336: rigid hair and weapons have exactly one bone/pivot attachment path."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


class UnifiedBoneMountTests(unittest.TestCase):
    def test_one_client_follower_no_old_controllers(self):
        self.assertFalse((ROOT / 'src/client/character/HairAttachmentController.luau').exists())
        self.assertFalse((ROOT / 'src/client/weapon/WeaponAttachmentController.luau').exists())
        controller = source('src/client/character/BoneMountedAttachmentController.luau')
        init = source('src/client/init.client.luau')
        self.assertEqual(controller.count('RunService.RenderStepped:Connect(update)'), 1)
        self.assertEqual(init.count('BoneMountedAttachmentController.Start()'), 1)
        self.assertNotIn('HairAttachmentController', init)
        self.assertNotIn('WeaponAttachmentController', init)
        self.assertIn('updateMount(character, hair, "hair")', controller)
        self.assertIn('updateMount(character, weapon, "weapon")', controller)
        self.assertIn('BoneModelMount.Place(model, state.grip, BoneModelMount.SocketFrame(state.bone, kind))', controller)
        self.assertNotIn('RuntimeBoneVisual', controller)
        self.assertNotIn(':Clone()', controller)

    def test_canonical_socket_and_grip_preserved_on_both_sides(self):
        shared = source('src/shared/rig/BoneModelMount.luau')
        character = source('src/server/character/CharacterAssemblyBuilder.luau')
        weapon = source('src/server/weapon/WeaponEquipService.luau')
        for statement in (
            'parent.TransformedWorldCFrame * targetBone.CFrame',
            'SocketFacing.FullFrame(frame, true)',
            'CFrame.Angles(math.rad(-90), 0, 0)',
            'local delta = socketFrame * grip.WorldCFrame:Inverse()',
            'model:PivotTo(delta * model:GetPivot())',
        ):
            self.assertIn(statement, shared)
        self.assertIn('BoneModelMount.Place(group, anchor, BoneModelMount.SocketFrame(target, "hair"))', character)
        self.assertIn('BoneModelMount.Place(weapon, grip, BoneModelMount.SocketFrame(targetBone, "weapon"))', weapon)
        self.assertIn('BoneModelMount.Place(weapon, grip, BoneModelMount.SocketFrame(bone, "weapon"))', weapon)

    def test_no_hair_physics_catchup_while_weapon_geometry_unchanged(self):
        builder = source('src/server/character/CharacterAssemblyBuilder.luau')
        rig = source('src/server/character/CharacterRigService.luau')
        weapon = source('src/server/weapon/WeaponEquipService.luau')
        attack = source('src/client/combat/AttackController.luau')
        self.assertNotIn('CharacterHairExtraWeld', builder)
        self.assertIn('piece.Anchored = true', builder)
        self.assertIn('object.Parent:GetAttribute("Game1HairCompound") == true', rig)
        self.assertIn('WeaponAttackVolume.StampWeaponBox(weapon)', weapon)
        self.assertIn('WeaponAttackVolume.ReadEquippedWeaponBox(character)', attack)

    def test_timeline_and_bow_consume_new_controller(self):
        timeline = source('system/studio-plugin/modules/StudioTimelinePreview.luau')
        controller = source('src/client/character/BoneMountedAttachmentController.luau')
        attack = source('src/client/combat/AttackController.luau')
        self.assertIn('character:FindFirstChild("BoneMountedAttachmentController")', timeline)
        self.assertIn('hairFollower.UpdateCharacter(preview)', timeline)
        self.assertIn('BoneMountedAttachmentController.GetBowReleaseOrigin(character)', attack)
        self.assertIn('BoneMountedAttachmentController.GetBowReleaseOrigin', controller)


if __name__ == '__main__':
    unittest.main()
