"""M307 narrow contracts: Firefly authoring and authoritative projectile behavior.

Static tests here are not a substitute for Roblox Studio animation/physics tests.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def source(path):
    return (ROOT / path).read_text(encoding='utf-8')


class FireflyTests(unittest.TestCase):
    def test_selected_bone_is_read_only(self):
        tuner = source('system/studio-plugin/fire-tuner/fire_bone.lua')
        selected = tuner.split('local function bindSelected()', 1)[1].split(
            'selectButton.MouseButton1Click', 1)[0]
        for forbidden in ('createFirefly()', 'createFire()', 'createLight()',
                          'CollectionService:AddTag', ':SetAttribute('):
            self.assertNotIn(forbidden, selected)
        self.assertIn('currentOrb = currentBone:FindFirstChild("Game1OrbEffect")', selected)
        self.assertIn('PRESET_KEY', tuner)
        self.assertIn('Tail -> Head', tuner)

    def test_firefly_uses_existing_bone_orb_controller(self):
        tuner = source('system/studio-plugin/fire-tuner/fire_bone.lua')
        runtime = source('src/client/world/BoneOrbController.luau')
        self.assertIn('Create / register Firefly', tuner)
        self.assertIn('CollectionService:AddTag(effect, "Game1LightOrb")', tuner)
        self.assertIn('GetTagged(TAG)', runtime)
        for attribute in ('RoamRadius', 'RoamSpeed', 'BobAmplitude', 'BobFrequency',
                          'Brightness', 'Range', 'Color', 'Shadows'):
            self.assertIn(attribute, tuner)
            self.assertIn(attribute, runtime)
        self.assertIn('math.noise', runtime)
        self.assertIn('MAX_ACTIVE = 32', runtime)
        self.assertIn('TICK = 1 / 30', runtime)
        self.assertNotIn('Instance.new("BodyVelocity")', runtime)
        self.assertNotIn('Instance.new("AlignPosition")', runtime)

    def test_firefly_is_portable_bone_effect_without_new_pipeline(self):
        src = source('system/studio-plugin/modules/StudioPlacedRigBoneEffects.luau')
        self.assertIn('if item.ClassName ~= "Attachment" then return false end', src)
        self.assertIn('local clone = item:Clone()', src)


class ArrowTests(unittest.TestCase):
    def test_bow_cannot_use_melee_volume(self):
        equip = source('src/server/weapon/WeaponEquipService.luau')
        volume = source('src/shared/combat/WeaponAttackVolume.luau')
        self.assertEqual(equip.count('WeaponAttackVolume.ClearWeaponBox(weapon)'), 2)
        self.assertIn('function WeaponAttackVolume.ClearWeaponBox', volume)
        server = source('src/server/combat/AttackService.luau')
        self.assertIn('local damageWindow = if isBow then nil', server)
        self.assertIn('if character and string.lower(tostring(character:GetAttribute("EquippedWeaponType") or "")) == "bow" then', server)

    def test_bow_range_clips_swept_ray_not_only_crosshair(self):
        bow = source('src/server/combat/BowProjectileService.luau')
        self.assertIn('character:GetAttribute("AttackRadius")', bow)
        self.assertIn('maxDistance = math.max(0, bowRange', bow)
        self.assertIn('math.max(0, state.maxDistance - state.distance)', bow)
        self.assertIn('displacement = displacement.Unit * remaining', bow)
        self.assertIn('or state.distance >= state.maxDistance', bow)
        self.assertIn('worldContact(character, origin, direction * bowRange)', bow)
        self.assertIn('worldContact(state.character, startPosition, displacement)', bow)
        self.assertNotIn('state.distance >= Policy.MaxDistance', bow)

    def test_precision_is_projectile_only(self):
        bow = source('src/server/combat/BowProjectileService.luau')
        spatial = source('src/server/combat/HitboxSpatialQueries.luau')
        hitbox = source('src/server/combat/EntityHitboxService.luau')
        self.assertIn('EntityHitboxService.RaycastAimRegions(state.character, startPosition, direction, distance, true)', bow)
        self.assertIn('rayHeadEllipsoidDistance', spatial)
        self.assertIn('projectilePrecision: boolean?', spatial)
        self.assertIn('else HitboxSpatialQueries.AimContact(binding, rayOrigin, direction, distanceLimit, frameSerial)', hitbox)
        self.assertIn('hit.Instance.Name ~= "RootCollider"', bow)

    def test_stuck_arrows_follow_skeleton_and_rigid_props(self):
        attach = source('src/server/combat/ArrowImpactAttachment.luau')
        bow = source('src/server/combat/BowProjectileService.luau')
        self.assertIn('bone.TransformedWorldCFrame:ToObjectSpace(visual:GetPivot())', attach)
        self.assertIn('visual:PivotTo(binding.bone.TransformedWorldCFrame * binding.localFrame)', attach)
        self.assertIn('RunService.Heartbeat:Connect(update)', attach)
        self.assertIn('connection:Disconnect()', attach)
        self.assertIn('weld.Name = "ArrowImpactWeld"', attach)
        self.assertIn('entityHit.model, entityHit.boneName)', bow)
        self.assertIn('Debris:AddItem(visual, 2.5)', bow)


if __name__ == '__main__':
    unittest.main()
