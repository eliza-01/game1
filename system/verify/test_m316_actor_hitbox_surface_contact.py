"""M316 bow contract regression: authority and contact are separate.

Static contract checks run without Roblox. Real skinned mesh collision/raycasts
and client Bone pose must additionally be verified in Studio Play.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class SurfaceAndDamageSeparation(unittest.TestCase):
    def test_damage_and_headshot_come_only_from_real_hitbox_intersection(self):
        hit=source('src/server/combat/BowHitscanService.luau')
        self.assertIn('EntityHitboxService.RaycastAimRegions(character, origin, direction, castDistance, true)',hit)
        self.assertIn('local headshot = snapshot.zone == "head"',hit)
        self.assertIn('DamageService.Apply(character, target',hit)
        self.assertNotIn('if state.capturedZone == "head"',hit)
        self.assertIn('if target then',hit)

    def test_surface_contact_is_impact_only_and_not_the_damage_point(self):
        hit=source('src/server/combat/BowHitscanService.luau')
        surface=source('src/server/combat/ArrowSurfaceContact.luau')
        self.assertEqual(hit.count('Surface.ResolveEntity('),1)
        self.assertIn('localContact = if part',hit)
        self.assertIn('if actor then',hit)
        self.assertLess(hit.index('Surface.ResolveEntity('),hit.index('DamageService.Apply(character, target'))
        self.assertIn('math.abs(contact.Distance - hitboxDistance) <= Policy.VisualSurfaceTolerance',surface)
        self.assertIn('VisualSurfaceSearchAhead',surface)
        self.assertNotIn('CanQuery = true',surface)

    def test_collider_priority_and_visibility_are_common_across_target_types(self):
        surface = source('src/server/combat/ArrowSurfaceContact.luau')
        self.assertIn('MeshPhysics.IsCollider(part.Name)', surface)
        self.assertIn('or part:GetAttribute("Game1DecoPhysicsOnly")', surface)
        self.assertIn('return castParts(origin, displacement, colliders, false)', surface)
        self.assertIn('or castParts(origin, displacement, colliders, true)', surface)
        self.assertIn('or castParts(origin, displacement, visuals, true)', surface)
        self.assertIn('params.FilterType = Enum.RaycastFilterType.Include', surface)
        self.assertIn('params.FilterDescendantsInstances = candidates', surface)
        self.assertIn('params.BruteForceAllSlow = brute', surface)
        self.assertIn('item:IsDescendantOf(visualScope)', surface)
        self.assertNotIn('boxRay(', surface) # no OBB or pivot-based visual fallback

    def test_visual_follows_real_part_on_rigid_fallback_and_old_bone_follow_remains(self):
        client=source('src/client/combat/BowShotVisualController.luau')
        self.assertIn('Instance.new("WeldConstraint")',client)
        self.assertIn('hitPart',client)
        self.assertIn('visual.Parent = sway',client)
        self.assertIn('bone.TransformedWorldCFrame:ToObjectSpace(visual:GetPivot())',client)
        self.assertIn('entry.bone.TransformedWorldCFrame * entry.localFrame',client)
        self.assertFalse((ROOT/'src/server/combat/ArrowImpactAttachment.luau').exists())

    def test_bow_only_melee_untouched(self):
        pose = source('src/client/combat/AimPoseController.luau')
        attack = source('src/server/combat/AttackService.luau')
        self.assertIn('local function signedYaw(', pose)
        self.assertIn('applyDamageInVolume(', attack)
        self.assertIn('WeaponAttackVolume.Build(', attack)


if __name__ == '__main__':
    unittest.main()
