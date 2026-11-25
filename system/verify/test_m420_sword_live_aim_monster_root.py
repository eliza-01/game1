"""M420: live cursor sword swing, independent legs, and aggro root-motion stabilization.

Numerical cases cover turn continuity; source checks cover frame/remote wiring.
Actual render/physics needs Studio Play and cannot be simulated by Python.
"""
from pathlib import Path
import math
import unittest

ROOT = Path(__file__).resolve().parents[2]

def source(path):
    return (ROOT / path).read_text(encoding='utf-8')


def shortest_step(previous, desired, blend):
    delta = math.atan2(math.sin(desired - previous), math.cos(desired - previous))
    return previous + delta * blend


class SwordLiveAimM420(unittest.TestCase):
    def test_complete_swing_has_live_camera_tracking_but_bounded_network(self):
        attack = source('src/client/combat/AttackController.luau')
        self.assertIn('local meleePresentationSequence = 0', attack)
        self.assertIn('meleePresentationSequence = sequence', attack)
        self.assertIn('meleePresentationUntil = os.clock() + attackDuration', attack)
        self.assertIn('MELEE_AIM_SEND_INTERVAL = 0.10', attack)
        self.assertIn('aimPoseController.UpdateTarget(target, direction)', attack)
        self.assertIn('movementController.UpdateAimFacingCompensation(target - root.Position)', attack)
        self.assertIn('now <= meleeHitEndAt and now >= nextMeleeAimAt', attack)
        self.assertIn('nextMeleeAimAt = now + MELEE_AIM_SEND_INTERVAL', attack)
        self.assertEqual(attack.count('RunService.RenderStepped:Connect('), 1)
        self.assertEqual(attack.count('meleeAimRemote:FireServer({'), 1)
        self.assertEqual(attack.count('bowAimRemote:FireServer({'), 1)
        self.assertIn('initialAimOrigin, initialAimDirection = aimPoseController.GetAimRay()', attack)
        self.assertIn('initialAimOrigin + initialAimDirection.Unit * AttackConfig.MaxAimDistance', attack)
        self.assertNotIn('GetAimPosition()', attack)
        self.assertNotIn('movementController.LockMovement(', attack)

    def test_server_uses_latest_pre_hitend_heading_not_attack_start_heading(self):
        store = source('src/server/combat/AttackSessionStore.luau')
        server = source('src/server/combat/AttackService.luau')
        self.assertIn('session.attackFacingDirection = direction', store)
        self.assertNotIn('if session.attackFacingDirection == nil then', store)
        self.assertIn('or session.environmentBlocked or session.hitResolved', server)
        self.assertIn('MeleeMovingFacing.Resolve(root.CFrame.LookVector, session.attackFacingDirection)', server)
        self.assertNotIn('Config.MovingMeleeMinimumSpeed', server)
        self.assertEqual(server.count('scheduleMeleeArc(player, character, root, serial, clientAttackId, clipId, contact,'), 1)
        self.assertIn('for _, contact in ipairs(meleePlan) do', server)
        self.assertIn('AttackSessionStore.MarkMeleeResolved', server)

    def test_yaw_wrap_and_reverse_targets_do_not_require_lower_body_turn(self):
        config = source('src/shared/combat/AttackConfig.luau')
        pose = source('src/client/combat/AimPoseController.luau')
        movement = source('src/client/character/MovementController.luau')
        self.assertIn('MovingAttackTorsoYawLimit = math.rad(100)', config)  # bow unchanged
        self.assertIn('MovingMeleeTorsoYawLimit = math.pi', config)
        self.assertIn('if melee then AttackConfig.MovingMeleeTorsoYawLimit else AttackConfig.MovingAttackTorsoYawLimit', pose)
        self.assertIn('pitchRotation * yawRotation * animatedRotation', pose)
        self.assertIn('controllerManager.FacingDirection = lowerBodyFacing', movement)
        yaw = math.radians(170)
        for angle in (179, -179, -160, -95, 0, 90, -175):
            next_yaw = shortest_step(yaw, math.radians(angle), 0.65)
            self.assertLessEqual(abs(next_yaw - yaw), math.pi * 0.65 + 1e-7)
            yaw = next_yaw
        self.assertGreater(abs(shortest_step(math.radians(179), math.radians(-179), 0.5)), math.radians(175))

    def test_aim_finish_and_respawn_do_not_leave_stale_attack_ids(self):
        attack = source('src/client/combat/AttackController.luau')
        self.assertIn('meleePresentationCharacter = nil', attack)
        self.assertIn('meleeHitEndAt = 0', attack)
        self.assertIn('if activeMeleeAimId == sequence then', attack)
        self.assertIn('or playerCharacter:GetAttribute("LifeState") ~= "Alive"', attack)


class MonsterCombatRootM420(unittest.TestCase):
    def test_combat_root_motion_owned_by_humanoid_on_all_aggro_phases(self):
        client = source('src/client/monster/MonsterAttackLocomotionController.luau')
        state = source('src/server/monster/MonsterCombatState.luau')
        rig = source('src/server/monster/MonsterRigBuilder.luau')
        self.assertIn('model:SetAttribute("MonsterCombatActive", true)', state)
        self.assertIn('model:SetAttribute("MonsterCombatActive", false)', state)
        self.assertIn('model:GetAttributeChangedSignal("MonsterCombatActive"):Connect(refreshActive)', client)
        self.assertIn('local combatActive = model:GetAttribute("MonsterCombatActive") == true and alive', client)
        self.assertIn('suppressCombatRootTranslation(entry)', client)
        self.assertIn('bone.Transform = bone.Transform.Rotation', client)
        self.assertNotIn('CFrame.new(0, transform.Position.Y, 0)', client)
        self.assertIn('local wantsComposition = pursuitActive', client) # legs only during pursuit
        self.assertIn('if not pursuitActive and not combatActive then', client)
        self.assertIn('MonsterAttackPursuitActive', client)
        self.assertIn('navigationRoot.CFrame = CFrame.new(', rig)
        self.assertIn('humanoid.HipHeight = NAVIGATION_HIP_HEIGHT', rig)
        self.assertNotIn('RunService.Heartbeat:Connect', client)

if __name__ == '__main__':
    unittest.main()
