"""M73 static contracts: physics-owned facing and motion-owned lower-body yaw.

These checks cannot simulate replication interpolation in Roblox Studio.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def source(relative):
    return (ROOT / relative).read_text(encoding="utf-8-sig")


class ActorDirectionReplicationTests(unittest.TestCase):
    def test_facing_is_physics_owned_and_cleanup_restores_humanoid(self):
        tracker = source('src/server/actor/ActorFacingTracker.luau')
        self.assertIn('Instance.new("AlignOrientation")', tracker)
        self.assertIn('Enum.OrientationAlignmentMode.OneAttachment', tracker)
        self.assertIn('align.Attachment0 = attachment', tracker)
        self.assertIn('align.MaxAngularVelocity = MAX_TURN_RATE', tracker)
        self.assertIn('align.MaxTorque = MAX_TORQUE', tracker)
        self.assertIn('entry.align:Destroy()', tracker)
        self.assertIn('entry.attachment:Destroy()', tracker)
        self.assertIn('entry.humanoid.AutoRotate = entry.autoRotate', tracker)
        self.assertNotIn('root.CFrame =', tracker)
        self.assertNotIn('model:PivotTo(', tracker)

    def test_monster_and_npc_share_damped_move_authority(self):
        shared = source('src/server/actor/ActorAttackPursuit.luau')
        monster = source('src/server/monster/MonsterAIService.luau')
        npc = source('src/server/npc/NpcCombatAIService.luau')
        self.assertIn('targetRoot.AssemblyLinearVelocity', shared)
        self.assertIn('math.exp(-TARGET_FILTER_RESPONSE', shared)
        self.assertIn('MAX_ACCELERATION * dt', shared)
        self.assertIn('ENTER_SPEED', shared)
        self.assertIn('EXIT_SPEED', shared)
        self.assertIn('self.humanoid:Move(direction, false)', shared)
        self.assertNotIn('MoveTo(', shared)
        for actor in (monster, npc):
            self.assertIn('AttackPursuit.new(root, humanoid)', actor)
            self.assertIn('attackPursuit:Step(', actor) if actor is monster else self.assertIn('pursuit:Step(', actor)
            self.assertIn('Facing.Track(', actor)
            self.assertIn('Facing.Stop(', actor)
        self.assertNotIn('agent.root.CFrame = CFrame.lookAt', monster)
        self.assertIn('maintainAttackPursuit(agent, target, serial)', monster)
        self.assertIn('beginAttack(agent, target, true)', npc)

    def test_legs_follow_motion_without_looking_at_target(self):
        pose = source('src/client/actor/ActorLowerBodyPose.luau')
        npc = source('src/client/actor/NpcAttackLocomotionController.luau')
        monster = source('src/client/monster/MonsterAttackLocomotionController.luau')
        self.assertIn('entry.root.AssemblyLinearVelocity', pose)
        self.assertIn('entry.lowerMovementDirection', pose)
        self.assertIn('math.exp(-VELOCITY_FILTER_RESPONSE', pose)
        self.assertNotIn('entry.root.CFrame.LookVector', pose)
        self.assertIn('LowerBodyPose.AlignToMovement(entry, dt)', npc)
        self.assertIn('ActorLowerBodyPose.AlignToMovement(entry, deltaTime)', monster)
        self.assertIn('entry.visualRootOffsetRotation', pose)

    def test_existing_attack_owner_and_root_home_snap_are_untouched(self):
        npc = source('src/server/npc/NpcCombatAIService.luau')
        monster = source('src/server/monster/MonsterAIService.luau')
        self.assertIn('agent.presentation.ContinueAttack(percent)', npc)
        self.assertIn('beginAttack(agent, target, true)', npc)
        self.assertIn('agent.root.CFrame = agent.home', npc)
        self.assertIn('AttackTimelineConfig.ResolveRuntime(', monster)


if __name__ == '__main__':
    unittest.main(verbosity=2)
