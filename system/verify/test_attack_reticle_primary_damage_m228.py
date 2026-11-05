"""M228 combat contract: one in-range reticle target plus blade multi-hit.

These are source/architecture checks; actual Luau hitbox intersection and
animation pose sequencing still require a Roblox Studio Play test.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


class AttackReticlePrimaryDamageM228Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resolver = read("src/server/combat/AttackDamageResolver.luau")
        cls.aim = read("src/shared/combat/AttackAimGeometry.luau")
        cls.attack = read("src/server/combat/AttackService.luau")
        cls.volume = read("src/shared/combat/WeaponAttackVolume.luau")

    def test_reticle_query_is_independent_of_blade_contacts(self):
        code = self.resolver
        self.assertIn('local contacts = EntityHitboxService.QueryDamageablesInBox(', code)
        self.assertIn('local candidate = EntityHitboxService.RaycastAimRegions(', code)
        self.assertNotIn('if #contacts > 0 and headshotTarget == nil', code)
        self.assertNotIn('if #contacts > 0 then', code)
        self.assertLess(code.index('RaycastAimRegions('), code.index('for _, target in ipairs(contacts) do'))

    def test_ray_adds_nearest_aimed_target_only_when_in_attack_radius(self):
        code = self.resolver
        condition = 'if candidate and AttackAimGeometry.HitWithinAttackRadius(root.Position, candidate.hitPosition, attackRange) then'
        insert = 'table.insert(contacts, 1, {'
        self.assertIn(condition, code)
        self.assertLess(code.index(condition), code.index(insert))
        self.assertIn('model = candidate.model,', code)
        self.assertIn('hitPosition = candidate.hitPosition,', code)
        self.assertIn('mode = "reticle_ray",', code)
        helper = self.aim.split('function AttackAimGeometry.HitWithinAttackRadius(', 1)[1].split('\nend', 1)[0]
        for token in ('typeof(hitPosition) == "Vector3"', 'finiteVector(hitPosition)',
                      'finiteNumber(attackRange)', 'attackRange > 0',
                      '(hitPosition - rootPosition).Magnitude <= attackRange + Config.AttackRadiusEpsilon'):
            self.assertIn(token, helper)

    def test_blade_multi_hit_is_not_restricted_by_reticle_range(self):
        code = self.resolver
        self.assertIn('for _, target in ipairs(contacts) do', code)
        # The range condition gates only the reticle insertion; do not filter
        # blade contacts by root distance (short-range sword length is intentional).
        self.assertNotIn('HitWithinAttackRadius(', code.split('for _, target in ipairs(contacts) do', 1)[1])
        self.assertIn('distanceToSphereExit(rootPosition, weaponTip, direction, radius)', self.volume)
        self.assertIn('bladeLength + extension', self.volume)

    def test_ray_plus_blade_same_target_applies_damage_only_once(self):
        code = self.resolver
        self.assertIn('local hitTargets = query.hitTargets or {}', code)
        self.assertIn('and hitTargets[model] ~= true', code)
        self.assertIn('hitTargets[model] = true', code)
        self.assertLess(code.index('hitTargets[model] = true'), code.index('hitCount += 1'))
        self.assertIn('DamageService.Apply(character, model, rawDamage, isHeadshot)', code)

    def test_only_one_aimed_headshot_and_no_automatic_blade_headshot(self):
        code = self.resolver
        self.assertIn('local isHeadshot = headshotTarget == nil', code)
        self.assertIn('and aimedRegion.zone == "head"', code)
        self.assertIn('and aimedRegion.model == model', code)
        self.assertIn('headshotTarget = model', code)
        self.assertIn('return hitCount, headshotTarget', code)
        self.assertNotIn('hit.geometryRole == "head"', code)
        self.assertIn('AttackSessionStore.SetHeadshotTarget(player, headshotTarget)', self.attack)

    def test_attack_window_bounce_and_unchanged_multisample_flow(self):
        code = self.attack
        self.assertIn('elapsed + 1e-4 < damageWindow.startTime', code)
        self.assertIn('elapsed > damageWindow.endTime + 1e-4', code)
        self.assertIn('WeaponEnvironmentCollision.Query(previousVolume, volume)', code)
        self.assertLess(code.index('triggerWeaponBounce(', code.index('local function applyAnimatedWeaponSweep(')),
                        code.index('hitCount += applyDamageInVolume('))
        self.assertIn('AttackSessionStore.HitTargets(player, character, serial, clientAttackId)', code)


if __name__ == '__main__':
    unittest.main()
