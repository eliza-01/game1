"""M419: moving melee uses Bow's leg authority and a bounded server-only arc.

No Roblox Studio physics is simulated. These model the yaw/travel contract
and assert the actual client/server dependency wiring, not only file presence.
"""
from pathlib import Path
import math
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


def read(relative):
    return (ROOT / relative).read_text(encoding='utf-8')


def normalized(v):
    magnitude = math.hypot(*v)
    return tuple(component / magnitude for component in v) if magnitude else (0, 0)


def rotate(v, angle):
    return v[0] * math.cos(angle) - v[1] * math.sin(angle), v[0] * math.sin(angle) + v[1] * math.cos(angle)


def signed_angle(a, b):
    return math.atan2(a[0] * b[1] - a[1] * b[0], a[0] * b[0] + a[1] * b[1])


def server_facing(root, aim, velocity=None):
    root = normalized(root)
    return normalized(aim) if aim is not None and math.hypot(*aim) >= 1e-5 else root


def bow_style_movement(axis):
    x, y = axis
    movement = normalized((x, y))
    if not movement[0] and not movement[1]:
        return movement, None, 'combat_idle'
    facing = (0, 1) if y < -0.001 else movement
    return movement, facing, 'walk' if y < -0.001 else 'run'


class MeleeMovementParityM419(unittest.TestCase):
    def test_all_run_strafe_and_diagonal_inputs_keep_travel_facing(self):
        for axis in ((0, 1), (1, 0), (-1, 0), (.7, .7), (-.7, .7), (1, 1), (-1, 1)):
            movement, feet, gait = bow_style_movement(axis)
            with self.subTest(axis=axis):
                self.assertEqual(feet, movement)
                self.assertEqual(gait, 'run')
        for axis in ((0, -1), (.4, -.6), (-.8, -.2)):
            movement, feet, gait = bow_style_movement(axis)
            with self.subTest(axis=axis):
                self.assertEqual(feet, (0, 1))
                self.assertEqual(gait, 'walk')
                self.assertLess(movement[1], 0)
        self.assertEqual(bow_style_movement((0, 0)), ((0, 0), None, 'combat_idle'))

    def test_server_sector_uses_validated_aim_even_when_legs_face_travel(self):
        root = (0, 1)
        for degrees in (-179, -110, -100, -90, -45, 0, 45, 90, 100, 110, 179):
            aim = rotate(root, math.radians(degrees))
            for speed in ((0, 0), (0, 12), (3, 3)):
                facing = server_facing(root, aim, speed)
                with self.subTest(aim_degrees=degrees, speed=speed):
                    self.assertAlmostEqual(facing[0], aim[0], places=6)
                    self.assertAlmostEqual(facing[1], aim[1], places=6)
        self.assertEqual(server_facing(root, None, (0, 12)), root)

    def test_melee_and_bow_use_same_leg_authority_but_not_bow_hit_remotes(self):
        attack = read('src/client/combat/AttackController.luau')
        movement = read('src/client/character/MovementController.luau')
        pose = read('src/client/combat/AimPoseController.luau')
        anim = read('src/client/character/animation/CharacterAnimationController.luau')
        self.assertRegex(attack, r'elseif not isBow and movementController then[\s\S]+?MeleeMaxResidualYaw\(\), true')
        self.assertIn('if liveAttackAim and moveDirection.Magnitude > 0.001 then', movement)
        self.assertIn('controllerManager.FacingDirection = lowerBodyFacing', movement)
        self.assertIn('moveDirection = cameraRelativeDirection(axis)', movement)
        self.assertIn('if moving then return end', movement)
        self.assertIn('if melee then AttackConfig.MovingMeleeTorsoYawLimit else AttackConfig.MovingAttackTorsoYawLimit', pose)
        self.assertIn('if state == "walk" then return "walk" end', anim)
        self.assertIn('return "combat_idle"', anim)
        self.assertEqual(attack.count('bowAimRemote:FireServer({'), 1)
        self.assertNotIn('movementController.LockMovement(', attack)

    def test_server_hits_environment_and_targets_with_single_shared_facing(self):
        service = read('src/server/combat/AttackService.luau')
        query = read('src/server/combat/MeleeTargetQuery.luau')
        damage = read('src/server/combat/AttackDamageResolver.luau')
        env = read('src/server/combat/MeleeEnvironmentContact.luau')
        sway = read('src/server/world/LandscapeSwayService.luau')
        session = read('src/server/combat/AttackSessionStore.luau')
        pure = read('src/shared/combat/MeleeMovingFacing.luau')
        self.assertIn('MeleeMovingFacing.Resolve(root.CFrame.LookVector', service)
        self.assertIn('MeleeEnvironmentContact.Query(root, reach, arcAngle, facing)', service)
        self.assertIn('LandscapeSwayService.MeleeArc(root, reach, arcAngle, facing)', service)
        self.assertIn('facingDirection=facing', service)
        self.assertIn('query.facingDirection', damage)
        self.assertIn('facingDirection or root.CFrame.LookVector', query)
        self.assertIn('facingDirection or root.CFrame.LookVector', env)
        self.assertIn('facingDirection or root.CFrame.LookVector', sway)
        self.assertIn('attackFacingDirection = direction', session)
        self.assertNotIn('if session.attackFacingDirection == nil then', session)
        self.assertIn('horizontalUnit(validatedAim) or horizontalUnit(rootFacing)', pure)
        self.assertNotIn('horizontalSpeed < minimumSpeed', pure)
        self.assertEqual(service.count('scheduleMeleeArc(player, character, root, serial, clientAttackId, clipId, hitEndEvent)'), 1)

    def test_speed_and_walk_modifier_not_forced_to_sprint(self):
        movement = read('src/client/character/MovementController.luau')
        registry = read('src/shared/weapon/WeaponRegistry.luau')
        sword = re.search(r'\["sword"\]\s*=\s*table\.freeze\(\{(.*?)\}\)', registry, re.S)
        self.assertIsNotNone(sword)
        self.assertIn('runSpeedMultiplier = 1', sword.group(1))
        self.assertIn('locomotionMode = "Run"', sword.group(1))
        self.assertIn('local nextMode = if walkActive then "Walk"', movement)
        self.assertIn('math.min(attackSpeed,', movement)
        self.assertIn('CharacterMovementConfig.RobloxSpeedAtRunMultiplier(', movement)


if __name__ == '__main__':
    unittest.main()
