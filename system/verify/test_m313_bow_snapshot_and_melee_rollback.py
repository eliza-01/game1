"""M313: bow snapshot-only targeting & impact representation contracts.

Independent numeric cases and source integration checks. Roblox Studio Play is
still required for Bone rendering, attachment placement and moving targets.
"""
from pathlib import Path
import math
import unittest

ROOT = Path(__file__).resolve().parents[2]

def source(name):
    return (ROOT / name).read_text(encoding="utf-8")

class MeleePreservation(unittest.TestCase):
    def test_m312_presentation_reverted_and_melee_keeps_its_hitbox_window(self):
        pose = source("src/client/combat/AimPoseController.luau")
        client = source("src/client/combat/AttackController.luau")
        server = source("src/server/combat/AttackService.luau")
        self.assertIn("local function signedYaw(", pose)
        self.assertNotIn("ThirdPersonAimGeometry", pose)
        self.assertIn("local direction = target - currentRoot.Position", pose)
        self.assertIn("CharacterAttackWindow.Resolve(action.timeline)", client)
        self.assertIn("publishWeaponPose()", client)
        self.assertIn("WeaponAttackVolume.ReadEquippedWeaponBox(character)", client)
        self.assertIn('local damageWindow = if isBow then nil else', server)
        self.assertFalse((ROOT / "src/shared/combat/ThirdPersonAimGeometry.luau").exists())
        self.assertFalse((ROOT / "src/client/dev/AimDebugController.luau").exists())

    def test_no_bow_per_frame_raycasts_or_network_updates(self):
        source_text = source("src/client/combat/AttackController.luau")
        section = source_text.split("RunService.RenderStepped:Connect(function(deltaTime)")[1].split(
            "local function attemptAttack()")[0]
        self.assertNotIn("bowAimRemote", section)
        self.assertNotIn("GetAimPosition", section)
        self.assertEqual(source_text.count("bowAimRemote:FireServer("), 1)
        self.assertIn("BowProjectileConfig.CaptureLeadSeconds", source_text)
        self.assertIn("bowCaptureSequence", source_text)

class BowSnapshot(unittest.TestCase):
    def test_server_only_once_near_release_and_frozen_world_point(self):
        attack=source('src/server/combat/AttackService.luau')
        hit=source('src/server/combat/BowHitscanService.luau')
        self.assertIn('if pending.snapshot or now > pending.releaseAt + BowProjectileConfig.CaptureGraceSeconds then return end',attack)
        self.assertIn('now < pending.releaseAt - BowProjectileConfig.CaptureWindowSeconds',attack)
        self.assertIn('pending.snapshot = BowHitscanService.Capture(',attack)
        self.assertIn('BowHitscanService.Release(player, character, pending.snapshot)',attack)
        self.assertIn('local point = if actor then actor.hitPosition',hit)
        self.assertIn('point = point',hit)
        self.assertIn('local headshot = snapshot.zone == "head"',hit)
        self.assertNotIn('Geometry.BallisticDirection',hit)
        self.assertNotIn('state.velocity - Vector3.yAxis',hit)
        self.assertIn('math.min(delta.Magnitude, bowRange)',hit)

    def test_captured_target_moving_does_not_change_flight_direction(self):
        launch = (0.5, 3, 0)
        captured = (2, 7, -4)
        moved = (22, 7, -4)
        vector = tuple(captured[i] - launch[i] for i in range(3))
        length = math.sqrt(sum(a*a for a in vector))
        fixed = tuple(a / length for a in vector)
        sample = tuple(launch[i] + fixed[i] * length for i in range(3))
        for value, target in zip(sample, captured):
            self.assertAlmostEqual(value, target)
        self.assertNotEqual(sample, moved)

    def test_close_high_enemy_camera_negative_pitch_launch_positive_pitch(self):
        camera, launch, head = (0, 13, 13), (0, 3, 0), (0, 7, -2)
        camera_pitch = math.degrees(math.atan2(head[1] - camera[1], 15))
        shot_pitch = math.degrees(math.atan2(head[1] - launch[1], 2))
        self.assertLess(camera_pitch, 0)
        self.assertGreater(shot_pitch, 0)

    def test_authoritative_range_socket_bound_and_first_collision(self):
        code=source('src/server/combat/BowHitscanService.luau')
        geo=source('src/shared/combat/BowAimGeometry.luau')
        self.assertIn('Geometry.ValidateLaunch(root,',code)
        self.assertIn('root.CFrame:PointToObjectSpace(launch)',code)
        self.assertIn('root.CFrame:PointToWorldSpace(localPoint)',code)
        self.assertIn('Policy.MaxLaunchSocketError',code)
        self.assertIn('worldContact(character, safeStart, candidate - safeStart)',code)
        self.assertIn('canReach(character, from, endPoint',code)
        self.assertIn('EntityHitboxService.RaycastAimRegions(character',code)
        self.assertIn('math.min(delta.Magnitude, bowRange)',code)
        self.assertIn('Policy.MaxLaunchOffset',geo)

class ArrowAppearance(unittest.TestCase):
    def test_lantern_uses_visible_mesh_not_proxy_pivot(self):
        surface=source('src/server/combat/ArrowSurfaceContact.luau')
        hit=source('src/server/combat/BowHitscanService.luau')
        self.assertIn('proxy.Name ~= "LandscapeSwayTarget"',surface)
        self.assertIn('part:IsA("MeshPart")',surface)
        self.assertIn('return castModel(model, origin, displacement)',surface)
        self.assertIn('Surface.Resolve(hit.Instance, origin, displacement)',hit)
        self.assertIn('table.insert(excluded, hit.Instance)',hit)
        self.assertIn('proxyContact.Distance <= hit.Distance',hit)
        self.assertNotIn('CanQuery = true',surface)

    def test_bone_follow_is_cosmetic_on_clients_and_weld_on_props(self):
        client=source('src/client/combat/BowShotVisualController.luau')
        self.assertIn('Instance.new("WeldConstraint")',client)
        self.assertIn('visual.Parent = sway',client)
        self.assertIn('bone.TransformedWorldCFrame:ToObjectSpace(visual:GetPivot())',client)
        self.assertIn('entry.bone.TransformedWorldCFrame * entry.localFrame',client)
        self.assertIn('Debris:AddItem(visual, Policy.StuckLifetime)',client)
        self.assertIn('BowShotVisualController',source('src/client/init.client.luau'))
        self.assertFalse((ROOT/'src/server/combat/ArrowImpactAttachment.luau').exists())
        self.assertFalse((ROOT/'src/client/combat/ArrowStuckVisualController.luau').exists())

if __name__ == '__main__':
    unittest.main()
