"""M418: sword run policy and visible-from-inside Studio range boundary.

Static contracts and numeric wall geometry only; physical yaw and transparency
must still be checked in Roblox Studio Play.
"""
from pathlib import Path
import math
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


class SwordRunM418(unittest.TestCase):
    def test_sword_attack_does_not_reduce_run_speed_or_lock_movement(self):
        registry = read('src/shared/weapon/WeaponRegistry.luau')
        sword = re.search(r'\["sword"\]\s*=\s*table\.freeze\(\{(.*?)\}\)', registry, re.S)
        self.assertIsNotNone(sword)
        self.assertIn('locomotionMode = "Run"', sword.group(1))
        self.assertIn('runSpeedMultiplier = 1', sword.group(1))
        attack = read('src/client/combat/AttackController.luau')
        self.assertIn('movementController.BeginAttackMovement(character:GetAttribute("EquippedWeaponType"), attackDuration)', attack)
        self.assertNotIn('movementController.LockMovement(', attack)
        movement = read('src/client/character/MovementController.luau')
        self.assertIn('local attackSpeed = CharacterMovementConfig.RobloxSpeedAtRunMultiplier(', movement)
        self.assertIn('controllerManager.BaseMoveSpeed = if walkActive then math.min(attackSpeed,', movement)
        self.assertIn('controllerManager.MovingDirection = moveDirection', movement)
        animation = read('src/client/character/animation/CharacterAnimationController.luau')
        self.assertIn('attackLowerBodyActive = true', animation)
        self.assertIn('if state == "walk" then return "walk" end', animation)

    def test_moving_melee_facing_never_writes_physics_root_cframe(self):
        movement = read('src/client/character/MovementController.luau')
        method = movement.split('local function applyAimFacingCompensation(', 1)[1].split('local function applyMovementMode(', 1)[0]
        moving_branch = re.search(r'if moving then\s*(.*?)\s*end', method, re.S)
        # There is an early Bow branch; check the final moving-melee clause explicitly.
        self.assertIn('if moving then return end', method)
        self.assertIn('if liveAttackAim and moveDirection.Magnitude > 0.001 then', movement)
        moving_guard = method.index('if moving then\n\t\t-- ControllerManager')
        cframe_write = method.index('navigationRoot.CFrame = CFrame.lookAt(')
        self.assertLess(moving_guard, cframe_write)
        self.assertNotIn('navigationRoot.CFrame =', method[moving_guard:cframe_write])
        self.assertIn('if moving then return end', method)  # bow behavior unchanged
        self.assertIn('navigationRoot.CFrame = CFrame.lookAt(', method)  # planted turning unchanged


class RangeInsideM418(unittest.TestCase):
    def test_inner_wall_is_client_only_noncolliding_and_double_sided(self):
        source = read('src/client/dev/DebugRangeCylinder.luau')
        self.assertIn('local HEIGHT = 200', source)
        self.assertIn('local WALL_TRANSPARENCY = 0.6', source)
        self.assertIn('local INNER_WALL_SEGMENTS = 64', source)
        self.assertIn('local panel = Instance.new("Part")', source)
        for setting in ('CanCollide = false', 'CanTouch = false',
                        'CanQuery = false', 'Anchored = true'):
            self.assertIn('panel.' + setting, source)
        self.assertIn('self._model:PivotTo(', source)
        self.assertIn('self._model.Parent = Workspace', source)
        self.assertIn('self._model.Parent = nil', source)
        self.assertIn('self._model:Destroy()', source)
        self.assertIn('self._part.Size = Vector3.new(HEIGHT, 2 * self._range, 2 * self._range)', source)
        for forbidden in ('FireServer(', 'InvokeServer(', 'RemoteEvent', 'GetDescendants('):
            self.assertNotIn(forbidden, source)

    def test_inner_wall_segments_meet_at_both_small_and_large_radii(self):
        count = 64
        half_angle = math.pi / count
        for radius in (1, 5, 50, 200, 1000):
            inradius = max(.3, radius * math.cos(half_angle) - .15)
            width = 2 * inradius * math.tan(half_angle) + .05
            # Chord planes form a closed inscribed polygon with a tiny seam overlap.
            self.assertGreaterEqual(width, 2 * inradius * math.tan(half_angle))
            farthest_corner = math.hypot(inradius, width / 2)
            self.assertLess(farthest_corner, radius + .05)


if __name__ == '__main__':
    unittest.main()
