"""M318: monster death phantom and live bow-facing integration guards.

The yaw and touch-stick model below exercises deterministic transitions. Luau
physics, Bone presentation and device input still require Roblox Studio Play.
"""
from __future__ import annotations

import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def wrap(angle: float) -> float:
    return math.atan2(math.sin(angle), math.cos(angle))


def step_root_yaw(current: float, aim: float, dt: float, moving=False,
                  torso_limit=math.radians(70), turn=0.28):
    """M319: physical root stays travel-owned; planted shots turn by overflow."""
    if moving:
        return current
    difference = wrap(aim - current)
    overflow = difference - max(-torso_limit, min(torso_limit, difference))
    blend = 1 - math.exp(-4 / turn * dt)
    return wrap(current + overflow * blend)


def backward_mode(y: float, is_touch: bool, live_bow: bool) -> bool:
    return y < -0.001 and (not is_touch or live_bow)


class MonsterPhantom(unittest.TestCase):
    def test_death_drops_combat_and_physics_before_animation(self):
        source = read("src/server/monster/MonsterDeathLifecycle.luau")
        policy = read("src/server/actor/ActorCollisionPolicy.luau")
        hitbox = read("src/server/combat/EntityHitboxService.luau")
        start = source.index('model:SetAttribute("Damageable", false)', source.index('local function beginDeath'))
        detach = source.index('EntityHitboxService.Detach(model)', start)
        phantom = source.index('ActorCollisionPolicy.MakePhantom(model)', detach)
        animation = source.index('DeathAnimationPolicy.Start(track,', phantom)
        self.assertLess(start, detach)
        self.assertLess(detach, phantom)
        self.assertLess(phantom, animation)
        self.assertIn('bindings[entity] = nil', hitbox)
        self.assertIn('debugFolder:Destroy()', hitbox)
        self.assertIn('for _, descendant in ipairs(actor:GetDescendants()) do', policy)
        for flag in ('CanCollide', 'CanTouch', 'CanQuery'):
            self.assertIn(f'descendant.{flag} = false', policy)
        self.assertNotIn('descendant.Anchored', policy)
        self.assertNotIn('descendant.Transparency', policy)
        # Respawn starts with a new instance; the dead one never regains contact.
        self.assertEqual(policy.count('function ActorCollisionPolicy.MakePhantom('), 1)

    def test_death_idle_and_respawn_still_own_visual_timeline(self):
        death = read("src/server/monster/MonsterDeathLifecycle.luau")
        spawner = read("src/server/monster/MonsterSpawnerService.luau")
        self.assertIn('DeathLifecycleService.BeginDeathIdle(model, entry.navigationRoot, entry.visual, function()', death)
        self.assertIn('releaseInstance(state, model, true)', death)
        self.assertIn('population:ScheduleRespawn(state, entry.diedAt)', spawner)
        self.assertIn('EntityHitboxService.Detach(model)', spawner)  # idempotent release


class LiveBowAim(unittest.TestCase):
    def test_camera_pose_tracks_through_complete_clip_but_damage_is_one_shot(self):
        attack = read('src/client/combat/AttackController.luau')
        movement = read('src/client/character/MovementController.luau')
        self.assertIn('bowPresentationUntil = os.clock() + attackDuration', attack)
        self.assertIn('aimPoseController.UpdateTarget(target)', attack)
        self.assertIn('movementController.UpdateAimFacingCompensation(target - root.Position)', attack)
        self.assertIn('attackDuration, AttackConfig.TorsoYawLimit, true', attack)
        self.assertIn('aimFacingLive = live == true', movement)
        self.assertIn('if liveBowAim then', movement)
        self.assertIn('if not aimFacingLive then\n\t\t\tclearAimFacingCompensation()', movement)
        self.assertIn('finishPresentation(bowCaptureSequence)', attack)
        self.assertIn('local origin, direction = aimPoseController.GetAimRay()', attack)
        self.assertEqual(attack.count('bowAimRemote:FireServer({'), 1)
        self.assertEqual(attack.count('weaponPoseRemote:FireServer({'), 1)
        frame = attack.split('RunService.RenderStepped:Connect(function(deltaTime)', 1)[1].split('local function attemptAttack()', 1)[0]
        self.assertNotIn('bowAimRemote:FireServer', frame)
        self.assertNotIn('Workspace:Raycast', frame)
        self.assertNotIn('GetAimPosition', frame)
        pose = read('src/client/combat/AimPoseController.luau')
        self.assertIn('targetPosition ~= nil and now <= activeUntil', pose)

    def test_planted_root_rotates_only_by_spine_overflow(self):
        direction = 0.0
        for _ in range(30):
            direction = step_root_yaw(direction, math.radians(150), 1/60)
        self.assertAlmostEqual(math.degrees(direction), 80, delta=1)
        # While locomoting root compensation cannot redirect the physical feet.
        for _ in range(30):
            direction = step_root_yaw(direction, math.radians(-150), 1/60, moving=True)
        self.assertAlmostEqual(math.degrees(direction), 80, delta=1)
        # Resume planted aiming: the reticle remains live, not attack-start locked.
        for _ in range(30):
            direction = step_root_yaw(direction, math.radians(-150), 1/60)
        self.assertAlmostEqual(abs(math.degrees(wrap(math.radians(-150) - direction))), 70, delta=1)
        fast = slow = 0.0
        for _ in range(60):
            fast = step_root_yaw(fast, math.radians(160), 1/120)
        for _ in range(15):
            slow = step_root_yaw(slow, math.radians(160), 1/30)
        self.assertAlmostEqual(fast, slow, delta=0.02)

    def test_down_stick_backpedals_only_during_live_bow(self):
        for y in (-1, -0.8, -0.3):
            self.assertTrue(backward_mode(y, False, False))  # keyboard S
            self.assertFalse(backward_mode(y, True, False))  # legacy touch free-running
            self.assertTrue(backward_mode(y, True, True))   # touch bow attack
        for y in (0, 0.6, 1):
            self.assertFalse(backward_mode(y, True, True))
        movement = read('src/client/character/MovementController.luau')
        self.assertIn('local backwardActive = backwardLocomotion(axis)', movement)
        self.assertIn('local nextDirectionMode = backwardActive and "Backward" or "Forward"', movement)
        self.assertIn('if liveBowAim then\n\t\t\tmoveDirection = cameraRelativeDirection(axis)', movement)
        self.assertNotIn('controllerManager.FacingDirection = aimFacingTargetDirection', movement)
        self.assertIn('controllerManager.FacingDirection = lowerBodyFacing', movement)
        self.assertIn('if moving then return end', movement)
        self.assertIn('clearAimFacingCompensation()', movement)


if __name__ == '__main__':
    unittest.main()
