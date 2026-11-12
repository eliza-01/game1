"""M291 static integration guards plus independent mathematical regression checks.

Studio is required to validate runtime Bone poses, projectile raycasts and replication.
These tests intentionally do not pretend that parsing source executes Luau.
"""
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


class Bow3DAimContracts(unittest.TestCase):
    def test_torso_pitch_layers_over_authored_pose_not_root(self):
        pose = read('src/client/combat/AimPoseController.luau')
        self.assertIn('desiredTorsoAngles', pose)
        self.assertIn('pitchRotation * yawRotation * animatedRotation', pose)
        self.assertIn('parentWorld:ToObjectSpace(desiredWorld)', pose)
        self.assertIn('StepAfterExternalPose', pose)
        self.assertIn('AimTorsoPitchDegrees', pose)
        self.assertNotIn('RootCollider.CFrame =', pose)

    def test_bow_uses_hands_facing_policy_and_live_lower_body_gait(self):
        movement = read('src/client/character/MovementController.luau')
        self.assertNotIn('if bowEquipped then', movement)
        self.assertIn('controllerManager.FacingDirection = moveDirection', movement)
        self.assertIn('moveDirection = backwardActive and', movement)
        self.assertIn('BeginAimFacingCompensation', movement)
        self.assertIn('BeginAttackMovement', movement)
        self.assertIn('WeaponAttackMovement.Resolve(weaponType)', movement)
        animation = read('src/client/character/animation/CharacterAnimationController.luau')
        self.assertIn('AttackUpperBodyComposer.Begin(', animation)

    def test_bow_has_no_fallback_to_hands_or_melee_sweep(self):
        resolver = read('src/client/character/animation/AnimationResolver.luau')
        self.assertIn('if weaponSet == "bow" then', resolver)
        self.assertIn('return nil', resolver.split('if weaponSet == "bow" then')[1].split('end')[0])
        attack = read('src/client/combat/AttackController.luau')
        self.assertIn('if isBow then', attack)
        self.assertIn('BowAimUpdate', attack)
        self.assertIn('aimOrigin = aimOrigin', attack)
        self.assertIn('aimDirection = aimDirection', attack)
        server = read('src/server/combat/AttackService.luau')
        self.assertIn('if weaponSet == "bow" then return nil', server)
        self.assertIn('return -- a bow cannot submit melee hitbox pose packets', server)

    def test_release_clock_and_damage_authority_stay_on_server(self):
        server = read('src/server/combat/AttackService.luau')
        projectile = read('src/server/combat/BowProjectileService.luau')
        self.assertIn('BowProjectileConfig.ReleaseEvent', server)
        self.assertIn('task.delay(releaseTime', server)
        self.assertIn('BowProjectileService.Release(player, character', server)
        self.assertIn('BowAimGeometry.Validate(root, payload.aimOrigin, payload.aimDirection)', server)
        self.assertIn('AttackSessionStore.IsCoolingDown(player, now)', server)
        self.assertIn('DamageService.Apply(state.character, target', projectile)
        self.assertIn('EntityHitboxService.RaycastAimRegions', projectile)
        self.assertIn('worldContact(state.character, startPosition, displacement)', projectile)
        self.assertIn('Workspace:Raycast(origin, displacement, params)', projectile)
        self.assertIn('BowProjectileConfig', projectile)

    def test_arrow_state_is_bounded_and_has_cancellation(self):
        policy = read('src/shared/combat/BowProjectileConfig.luau')
        projectile = read('src/server/combat/BowProjectileService.luau')
        self.assertIn('MaxActivePerPlayer = 3', policy)
        self.assertIn('MaxLifetime = 3.6', policy)
        self.assertIn('count >= Policy.MaxActivePerPlayer', projectile)
        self.assertIn('os.clock() - state.born >= Policy.MaxLifetime', projectile)
        self.assertIn('Players.PlayerRemoving:Connect', projectile)
        self.assertIn('state.player.Character ~= state.character', projectile)
        factory = read('src/server/combat/ArrowVisualFactory.luau')
        self.assertIn('child.CanCollide = false', factory)
        self.assertIn('child.CanQuery = false', factory)

    def test_aim_validation_and_parallax_safety(self):
        geometry = read('src/shared/combat/BowAimGeometry.luau')
        self.assertIn('AttackAimGeometry.Normalize', geometry)
        self.assertIn('root.CFrame:VectorToObjectSpace(unitDirection)', geometry)
        self.assertIn('Policy.MaxAimYaw', geometry)
        self.assertIn('Policy.MinAimPitch', geometry)
        self.assertIn('Policy.MaxAimPitch', geometry)
        projectile = read('src/server/combat/BowProjectileService.luau')
        self.assertIn('muzzlePosition(root)', projectile)
        self.assertIn('spawnPosition - root.Position', projectile)
        self.assertIn('blockedAt', projectile)
        self.assertNotIn('clientHitTarget', projectile)

    def test_camera_can_look_up_and_down_for_bow_and_melee(self):
        camera = read('src/shared/character/CharacterConfig.luau')
        self.assertIn('CameraMinPitch = math.rad(-65)', camera)
        self.assertIn('CameraMaxPitch = math.rad(60)', camera)
        controller = read('src/client/character/CameraController.luau')
        self.assertIn('CharacterConfig.CameraMinPitch', controller)
        self.assertIn('CharacterConfig.CameraMaxPitch', controller)

    def test_ballistic_discriminant_basics(self):
        # Cross-check the published policy's low-arc formula independently.
        speed, gravity, distance, height = 145.0, 38.0, 80.0, 10.0
        discriminant = speed**4 - gravity * (gravity * distance**2 + 2 * height * speed**2)
        self.assertGreater(discriminant, 0)
        angle = math.atan((speed**2 - math.sqrt(discriminant)) / (gravity * distance))
        t = distance / (speed * math.cos(angle))
        self.assertAlmostEqual(speed * math.sin(angle) * t - 0.5 * gravity * t**2, height, places=7)
        self.assertLess(angle, math.pi / 2)

    def test_no_generated_manifest_or_asset_id_touched(self):
        policy = read('src/shared/combat/BowProjectileConfig.luau')
        self.assertNotIn('assetId', policy)
        self.assertNotIn('ModelAssetId', policy)
        self.assertNotIn('attack-timelines.json', read('src/server/combat/BowProjectileService.luau'))


if __name__ == '__main__':
    unittest.main()
