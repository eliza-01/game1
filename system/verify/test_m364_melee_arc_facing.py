"""M364: equip-cached melee sector facing; no Roblox physics simulated.

Numerical cases verify the yaw budget and sector containment. Source contracts
verify the runtime wiring. Live turning/replication still requires Studio Play.
"""
from pathlib import Path
import math
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


POLICY = read('src/shared/combat/MeleeFacingPolicy.luau')
CONFIG = read('src/shared/combat/AttackConfig.luau')
MOVEMENT = read('src/client/character/MovementController.luau')
ATTACK = read('src/client/combat/AttackController.luau')
SERVER = read('src/server/combat/MeleeTargetQuery.luau')


class MeleeArcFacingM364(unittest.TestCase):
    def test_equipped_arc_and_torso_budget_keep_reticle_inside_sector(self):
        ratio = float(re.search(r'INNER_ARC_FRACTION\s*=\s*([\d.]+)', POLICY).group(1))
        torso_deg = float(re.search(r'TorsoYawLimit\s*=\s*math.rad\((\d+)\)', CONFIG).group(1))
        self.assertGreater(ratio, 0)
        self.assertLess(ratio, 1)
        for arc in (1, 10, 35, 60, 108, 140, 180, 270, 359, 360):
            residual = 180 if arc == 360 else min(torso_deg, (arc / 2) * ratio)
            for aim_yaw in (-180, -150, -110, -70, -50, -10, 0, 10, 50, 70, 110, 150, 180):
                torso = max(-residual, min(aim_yaw, residual))
                root_turn = aim_yaw - torso
                sector_offset = aim_yaw - root_turn
                self.assertLessEqual(abs(sector_offset), arc / 2 + 1e-8, (arc, aim_yaw))
                if arc < 360 and abs(aim_yaw) > (arc / 2) * ratio:
                    self.assertGreater(abs(root_turn), 0, (arc, aim_yaw))
                if abs(aim_yaw) <= residual:
                    self.assertEqual(root_turn, 0, (arc, aim_yaw))
        self.assertIn('math.min(AttackConfig.TorsoYawLimit, math.rad(angle * 0.5) * INNER_ARC_FRACTION)', POLICY)
        self.assertIn('if angle >= 360 then', POLICY)

    def test_cache_is_reevaluated_on_equip_and_cleared_on_respawn(self):
        self.assertIn('local meleeArcConnection: RBXScriptConnection? = nil', MOVEMENT)
        self.assertIn('meleeMaxResidualYaw = MeleeFacingPolicy.MaxResidualYaw(newCharacter:GetAttribute("MeleeArcAngle"))', MOVEMENT)
        self.assertIn('GetAttributeChangedSignal("MeleeArcAngle"):Connect(refreshMeleeFacing)', MOVEMENT)
        self.assertIn('meleeArcConnection:Disconnect()', MOVEMENT)
        self.assertIn('function MovementController.MeleeMaxResidualYaw()', MOVEMENT)
        update = MOVEMENT.split('local function updateMovement(', 1)[1].split('function MovementController.SetTouchMovement', 1)[0]
        self.assertNotIn('MaxResidualYaw(', update)
        self.assertNotIn('GetAttribute("MeleeArcAngle")', update)

    def test_stationary_and_moving_melee_keep_turn_until_hitend(self):
        self.assertIn('elseif not isBow and movementController then', ATTACK)
        self.assertIn('movementController.MeleeMaxResidualYaw()', ATTACK)
        self.assertIn('attackDuration,', ATTACK)
        self.assertIn('movementController.MeleeMaxResidualYaw(), true', ATTACK)
        self.assertIn('if liveAttackAim and moveDirection.Magnitude > 0.001 then', MOVEMENT)
        self.assertIn('controllerManager.FacingDirection = lowerBodyFacing', MOVEMENT)
        self.assertIn('if moving then return end', MOVEMENT)
        self.assertIn('yaw - math.clamp(yaw, -aimFacingMaxResidualYaw, aimFacingMaxResidualYaw)', MOVEMENT)
        self.assertIn('facingDirection or root.CFrame.LookVector', SERVER)
        self.assertIn('MeleeMovingFacing.Resolve(root.CFrame.LookVector', read('src/server/combat/AttackService.luau'))

    def test_bow_and_server_contact_are_unchanged(self):
        self.assertIn('attackDuration, AttackConfig.TorsoYawLimit, true', ATTACK)
        self.assertIn('movementController.UpdateAimFacingCompensation(target - root.Position)', ATTACK)
        self.assertIn('if aimFacingLive then', MOVEMENT)
        self.assertIn('if moving then return end', MOVEMENT)
        self.assertIn('MeleeTargetQuery.Find', read('src/server/combat/AttackDamageResolver.luau'))


if __name__ == '__main__':
    unittest.main()
