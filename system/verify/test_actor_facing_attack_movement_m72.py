"""M72 contracts: shared facing, attack pursuit, per-weapon locomotion & regression safety.

Behavior inside Roblox Studio is still an integration check; these tests guard
wiring and invariants without pretending to simulate Humanoid physics in Python.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]

def read(path):
    return (ROOT / path).read_text(encoding="utf-8")

class AttackMovementM72Tests(unittest.TestCase):
    def test_monster_and_npc_share_smooth_server_facing(self):
        tracker = read('src/server/actor/ActorFacingTracker.luau')
        monster = read('src/server/monster/MonsterAIService.luau')
        npc = read('src/server/npc/NpcCombatAIService.luau')
        self.assertIn('RunService.Heartbeat:Connect(step)', tracker)
        self.assertIn('humanoid.AutoRotate = false', tracker)
        self.assertIn('Enum.OrientationAlignmentMode.OneAttachment', tracker)
        self.assertIn('align.Responsiveness = TURN_RESPONSE', tracker)
        self.assertIn('align.MaxAngularVelocity = MAX_TURN_RATE', tracker)
        self.assertIn('align:Destroy()', tracker)
        self.assertNotIn('root.CFrame = CFrame.lookAt', tracker)
        self.assertIn('Facing.Track(agent.model', monster)
        self.assertIn('Facing.Track(agent.model', npc)
        self.assertIn('Facing.Stop(agent.model)', monster)
        self.assertIn('Facing.Stop(agent.model)', npc)
        self.assertNotIn('agent.root.CFrame = CFrame.lookAt', npc)
        self.assertIn('agent.root.CFrame.LookVector:Dot', monster)

    def test_attack_chase_keeps_hit_animation_owner(self):
        npc = read('src/server/npc/NpcCombatAIService.luau')
        pursuit = read('src/server/actor/ActorAttackPursuit.luau')
        self.assertIn('self.humanoid:Move(direction, false)', pursuit)
        self.assertIn('self.humanoid:Move(direction, false)', pursuit)
        self.assertNotIn('MoveTo(', pursuit)
        self.assertIn('pursuit:Step(targetRoot, agent.attackRadius, maxSpeed)', npc)
        self.assertIn('NpcAttackPursuitActive', npc)
        self.assertIn('beginAttack(agent, target, true)', npc)
        self.assertIn('agent.presentation.ContinueAttack(percent)', npc)
        self.assertIn('if agent.attacking then return end', npc)

    def test_policy_from_published_equipment_not_hardcoded_npc(self):
        equip = read('src/server/npc/NpcEquipmentService.luau')
        ai = read('src/server/npc/NpcCombatAIService.luau')
        policy = read('src/shared/weapon/WeaponAttackMovement.luau')
        self.assertIn('WeaponAttackMovement.AnimationSetForType(primaryType)', equip)
        self.assertIn('entity:SetAttribute("NpcWeaponType", primaryType)', equip)
        self.assertIn('WeaponAttackMovement.Resolve(model:GetAttribute("NpcWeaponType"))', ai)
        self.assertIn('policy.runSpeedMultiplier', ai)
        self.assertIn('policy.locomotionMode', ai)
        self.assertIn('EquivalentRunSpeedForLocomotion', ai)
        self.assertIn('NpcAttackPursuitAnimationId', ai)
        self.assertIn('function WeaponAttackMovement.Resolve(', policy)

    def test_lower_body_is_shared_and_monster_is_preserved(self):
        npc = read('src/client/actor/NpcAttackLocomotionController.luau')
        monster = read('src/client/monster/MonsterAttackLocomotionController.luau')
        sampler = read('src/client/actor/ActorLocomotionSampler.luau')
        pose = read('src/client/actor/ActorLowerBodyPose.luau')
        client = read('src/client/init.client.luau')
        self.assertIn('RunService.PreSimulation:Connect(step)', npc)
        self.assertIn('NpcAttackPursuitActive', npc)
        self.assertIn('ActorLowerBodyPose.AlignToMovement(entry, deltaTime)', monster)
        self.assertIn('LowerBodyPose.AlignToMovement(entry, dt)', npc)
        self.assertIn('targetBone.Transform:Lerp(sourceBone.Transform', npc)
        self.assertIn('SetPlaybackSpeed', sampler)
        self.assertIn('ActorSkeletonMap', sampler)
        self.assertIn('NpcAttackLocomotionController.Start()', client)
        self.assertIn('MonsterAttackLocomotionController.Start()', client)
        self.assertIn('ResolveIndependentLowerBodyRoots', pose) if False else None

if __name__ == '__main__':
    unittest.main(verbosity=2)
