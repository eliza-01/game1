"""M335: bow hitscan uses the same viewport ray on mobile and desktop.

The numeric OBB scenarios exercise the ordering failure behind the root-bounds
fallback. Luau runtime confirmation still requires Roblox Studio/Android Play.
"""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def ray_box(origin, direction, center, size):
    """Axis-aligned specialization of the runtime slab ray/OBB intersection."""
    near, far = 0.0, 100.0
    for o, d, c, side in zip(origin, direction, center, size):
        half = side / 2
        if abs(d) < 1e-8:
            if abs(o - c) > half:
                return None
            continue
        one, two = (c - half - o) / d, (c + half - o) / d
        near, far = max(near, min(one, two)), min(far, max(one, two))
        if near > far:
            return None
    return near


def zone_for_fallback(origin, direction):
    # A headbox nested in an intentionally full RootCollider: the first ray
    # collision is with BODY even when the reticle is physically over HEAD.
    root = ray_box(origin, direction, (0, 0, 0), (4, 6, 4))
    head = ray_box(origin, direction, (0, 2.15, 0), (1.3, 1.4, 1.3))
    if head is not None:
        return "head", head, root
    return ("body" if root is not None else None), root, root


class BowHeadshotMobileM335(unittest.TestCase):
    def test_nested_head_wins_in_fallback_even_behind_root_surface(self):
        zone, head_at, root_at = zone_for_fallback((0, 2.15, 10), (0, 0, -1))
        self.assertEqual(zone, 'head')
        self.assertLess(root_at, head_at) # old nearest-OBB logic wrongly said BODY
        q = source('src/server/combat/HitboxSpatialQueries.luau')
        self.assertIn('binding.mode == "root_bounds_fallback" and bestZone == "head"', q)
        self.assertIn('distance ~= nil and not fallbackHeadContact', q)

    def test_body_and_empty_ray_do_not_get_false_headshot(self):
        self.assertEqual(zone_for_fallback((0, 0, 10), (0, 0, -1))[0], 'body')
        self.assertIsNone(zone_for_fallback((4.5, 2.15, 10), (0, 0, -1))[0])
        self.assertEqual(zone_for_fallback((0.85, 2.15, 10), (0, 0, -1))[0], 'body')

    def test_precise_mesh_mode_keeps_nearest_contact(self):
        q = source('src/server/combat/HitboxSpatialQueries.luau')
        self.assertIn('binding.mode == "root_bounds_fallback"', q)
        self.assertIn('distance < bestDistance - SAT_EPSILON', q)
        self.assertIn('rayHeadEllipsoidDistance(', q)
        self.assertIn('bodyBox.size * 0.90', q)

    def test_mobile_and_desktop_use_same_ray_to_authoritative_hitscan(self):
        camera = source('src/client/character/CameraController.luau')
        self.assertIn('ViewportPointToRay(v.X * cameraSettings.cursorX, v.Y * cameraSettings.cursorY)', camera)
        input_module = source('src/client/combat/AttackController.luau')
        self.assertIn('local origin, direction = aimPoseController.GetAimRay()', input_module)
        self.assertIn('bowAimRemote:FireServer({', input_module)
        self.assertIn('aimDirection = direction', input_module)
        service = source('src/server/combat/AttackService.luau')
        self.assertIn('BowAimGeometry.Validate(root, payload.aimOrigin, payload.aimDirection)', service)
        hitscan = source('src/server/combat/BowHitscanService.luau')
        self.assertIn('EntityHitboxService.RaycastAimRegions(character, origin, direction, castDistance, true)', hitscan)
        self.assertIn('local headshot = snapshot.zone == "head"', hitscan)
        self.assertIn('AttackConfig.HeadshotDamageMultiplier', hitscan)
        self.assertIn('target:SetAttribute("LastHeadshot", headshot)', hitscan)
        # Acquisition still intentionally aims neck: this patch must NOT alter it.
        self.assertIn('return upperSpine or head', source('src/client/character/MobileAutoAimTargeting.luau'))

    def test_studio_only_hitbox_preview_is_unrelated_to_damage(self):
        hitbox = source('src/server/combat/EntityHitboxService.luau')
        self.assertIn('if not RunService:IsStudio() then', hitbox)
        self.assertIn('CombatHitboxDebugData', hitbox)
        self.assertIn('HitboxSpatialQueries.AimContact', hitbox)


if __name__ == '__main__':
    unittest.main()
