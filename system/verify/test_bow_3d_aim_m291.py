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
        self.assertIn('moveDirection = backwardActive and backwardRelativeDirection(', movement)
        self.assertIn('if liveBowAim then', movement)
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
        server=read('src/server/combat/AttackService.luau')
        hit=read('src/server/combat/BowHitscanService.luau')
        self.assertIn('BowProjectileConfig.ReleaseEvent',server)
        self.assertIn('task.delay(releaseTime',server)
        self.assertIn('BowHitscanService.Release(player, character',server)
        self.assertIn('AttackSessionStore.IsCoolingDown(player, now)',server)
        self.assertIn('DamageService.Apply(character, target',hit)
        self.assertIn('EntityHitboxService.RaycastAimRegions(character',hit)
        self.assertIn('Workspace:Raycast(origin, displacement, params)',hit)
        self.assertNotIn('RunService.Heartbeat:Connect',hit)

    def test_arrow_state_is_bounded_and_has_cancellation(self):
        policy=read('src/shared/combat/BowProjectileConfig.luau')
        client=read('src/client/combat/BowShotVisualController.luau')
        factory=read('src/shared/combat/ArrowVisualFactory.luau')
        self.assertIn('MaxClientVisuals = 64',policy)
        self.assertIn('StuckLifetime = 2.5',policy)
        self.assertIn('renderConnection:Disconnect()',client)
        self.assertIn('while #flights + #attachedBones > Policy.MaxClientVisuals',client)
        self.assertIn('node.CanCollide = false',factory)
        self.assertIn('child.CanQuery = false',factory)

    def test_aim_validation_and_parallax_safety(self):
        geo=read('src/shared/combat/BowAimGeometry.luau')
        server=read('src/server/combat/BowHitscanService.luau')
        self.assertIn('AttackAimGeometry.Normalize',geo)
        self.assertIn('root.CFrame:VectorToObjectSpace(unitDirection)',geo)
        self.assertIn('Policy.MaxAimYaw',geo)
        self.assertIn('Policy.MinAimPitch',geo)
        self.assertIn('Policy.MaxAimPitch',geo)
        self.assertIn('Geometry.ValidateLaunch(root,',server)
        self.assertIn('worldContact(character, safeStart, candidate - safeStart)',server)
        self.assertIn('OcclusionTolerance',server)
        self.assertNotIn('clientHitTarget',server)

    def test_camera_can_look_up_and_down_for_bow_and_melee(self):
        camera = read('src/shared/character/CharacterConfig.luau')
        self.assertIn('CameraMinPitch = math.rad(-65)', camera)
        self.assertIn('CameraMaxPitch = math.rad(60)', camera)
        controller = read('src/client/character/CameraController.luau')
        self.assertIn('CharacterConfig.CameraMinPitch', controller)
        self.assertIn('CharacterConfig.CameraMaxPitch', controller)

    def test_straight_snapshot_flight_basics(self):
        # M313 intentionally replaces ballistic arc with one frozen, straight ray.
        start, target = (0, 3, 0), (2, 8, -5)
        vector = tuple(target[i] - start[i] for i in range(3))
        distance = math.sqrt(sum(value * value for value in vector))
        velocity = tuple(value * 145.0 / distance for value in vector)
        time_to_target = distance / 145.0
        predicted = tuple(start[i] + velocity[i] * time_to_target for i in range(3))
        for actual, expected in zip(predicted, target):
            self.assertAlmostEqual(actual, expected, places=7)

    def test_no_generated_manifest_or_asset_id_touched(self):
        policy=read('src/shared/combat/BowProjectileConfig.luau')
        self.assertNotIn('assetId',policy)
        self.assertNotIn('ModelAssetId',policy)
        self.assertNotIn('attack-timelines.json',read('src/server/combat/BowHitscanService.luau'))

if __name__ == '__main__':
    unittest.main()
