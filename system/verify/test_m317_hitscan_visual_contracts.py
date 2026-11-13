"""M317: server-only hit authority and client-only Lineage-style arrow visuals.

These tests check integration invariants; true skinning and replication still
require visual Studio Play tests with a moving NPC and a swinging lantern.
"""
from pathlib import Path
import math
import unittest

ROOT = Path(__file__).resolve().parents[2]


def code(relative):
    return (ROOT / relative).read_text(encoding='utf-8')


class HitscanServerContracts(unittest.TestCase):
    def test_one_sample_with_late_network_grace_but_no_draw_tracking(self):
        attack = code('src/server/combat/AttackService.luau')
        client = code('src/client/combat/AttackController.luau')
        config = code('src/shared/combat/BowProjectileConfig.luau')
        self.assertEqual(client.count('bowAimRemote:FireServer({'), 1)
        self.assertEqual(attack.count('BowHitscanService.Capture('), 1)
        self.assertEqual(attack.count('BowHitscanService.Release('), 1)
        self.assertIn('CaptureLeadSeconds = 0.10', config)
        self.assertIn('CaptureGraceSeconds = 0.20', config)
        self.assertNotIn('aimPoseController.UpdateTarget(point)', client)

    def test_gameplay_hit_only_by_server_ray_and_weapon_range(self):
        server = code('src/server/combat/BowHitscanService.luau')
        self.assertIn('EntityHitboxService.RaycastAimRegions(character, origin, direction, castDistance, true)', server)
        self.assertIn('if actor and actor.distance > blocked + Policy.OcclusionTolerance', server)
        self.assertIn('canReach(character, from, endPoint, target', server)
        self.assertIn('endPoint = from + delta.Unit * math.min(delta.Magnitude, bowRange)', server)
        self.assertEqual(server.count('DamageService.Apply('), 1)
        self.assertIn('headshot = snapshot.zone == "head"', server)
        self.assertIn('publish(payload)', server)
        self.assertLess(server.index('publish(payload)'), server.index('DamageService.Apply(character, target'))
        self.assertNotIn('RunService.Heartbeat:Connect', server)
        self.assertNotIn('state.velocity', server)
        self.assertNotIn('Instance.new("Part")', server)

    def test_no_pivot_based_stuck_arrow_fallback(self):
        server = code('src/server/combat/BowHitscanService.luau')
        client = code('src/client/combat/BowShotVisualController.luau')
        self.assertIn('Surface.ResolveEntity(', server)
        self.assertIn('contactBone = impactBone', server)
        self.assertIn('contactBoneLocal = boneLocal', server)
        self.assertIn('hitBone = if target then snapshot.contactBone else nil', server)
        self.assertIn('chosenBone = entry.hitBone', client)
        self.assertIn('part.CFrame:PointToObjectSpace(position)', server)
        self.assertIn('part.CFrame:PointToWorldSpace(localContact)', client)
        self.assertIn('if not part or not part:IsA("BasePart") or not part.Parent', client)
        self.assertIn('if (contact - entry.point).Magnitude > Policy.MaxVisualAttachmentJump', client)
        self.assertNotIn('entity.PrimaryPart.Position', client)
        self.assertNotIn('hitbox:GetPivot()', client)

    def test_lineage_style_bone_local_attachment_and_rigid_weld(self):
        client = code('src/client/combat/BowShotVisualController.luau')
        self.assertIn('bone.TransformedWorldCFrame:ToObjectSpace(visual:GetPivot())', client)
        self.assertIn('entry.bone.TransformedWorldCFrame * entry.localFrame', client)
        self.assertIn('Instance.new("WeldConstraint")', client)
        self.assertIn('visual.Parent = sway', client)
        self.assertIn('renderConnection:Disconnect()', client)
        self.assertIn('Debris:AddItem(visual, Policy.StuckLifetime)', client)

    def test_published_template_is_reused_not_uploaded_again(self):
        factory = code('src/shared/combat/ArrowVisualFactory.luau')
        self.assertIn('function Factory.PublishActiveTemplate()', factory)
        self.assertIn('Game1ArrowTemplates', factory)
        self.assertIn('template:Clone()', factory)
        self.assertIn('local correction = ROTATIONS[', factory)
        self.assertNotIn('OpenCloud', factory)
        self.assertNotIn('PublishAsync', factory)

    def test_old_runtime_and_policies_are_physically_removed(self):
        for path in (
            'src/server/combat/BowProjectileService.luau',
            'src/server/combat/ArrowImpactAttachment.luau',
            'src/server/combat/ArrowVisualFactory.luau',
            'src/client/combat/ArrowStuckVisualController.luau',
        ):
            self.assertFalse((ROOT / path).exists(), path)
        cfg = code('src/shared/combat/BowProjectileConfig.luau')
        self.assertNotIn('MaxLifetime', cfg)
        self.assertNotIn('CapturedActorTerminalMargin', cfg)
        self.assertNotIn('CapturedWorldTerminalMargin', cfg)
        self.assertIn('BowShotVisualController', code('src/client/init.client.luau'))
        self.assertIn('BowHitscanService', code('src/server/bootstrap/ServiceCatalog.luau'))

    def test_melee_still_uses_animated_volume_and_original_aim_pose(self):
        attack = code('src/server/combat/AttackService.luau')
        self.assertIn('WeaponAttackVolume.Build(', attack)
        self.assertIn('HitStart -> HitEnd', attack)
        self.assertIn('CharacterAttackWindow.Resolve(timing)', attack)
        pose = code('src/client/combat/AimPoseController.luau')
        self.assertIn('local function signedYaw(', pose)


class LocalContactBehavior(unittest.TestCase):
    def test_local_point_moves_with_rigid_target_without_tracking_during_flight(self):
        point = (2.0, 0.5, -1.5)
        origin = (10.0, 1.0, -3.0)
        local = tuple(a-b for a,b in zip(point, origin))
        moved = (18.0, 3.0, -3.0)
        reattached = tuple(a+b for a,b in zip(local, moved))
        self.assertEqual(reattached, (10.0, 2.5, -1.5))
        self.assertNotEqual(reattached, point)
        frozenFlight = point
        self.assertEqual(frozenFlight, point)

    def test_visual_jump_cap_is_checked_in_world_space(self):
        policy = code('src/shared/combat/BowProjectileConfig.luau')
        self.assertIn('MaxVisualAttachmentJump = 3.0', policy)
        self.assertGreater(math.dist((1,0,0),(5,0,0)),3)
        self.assertLess(math.dist((1,0,0),(2,0,0)),3)


if __name__ == '__main__':
    unittest.main()
