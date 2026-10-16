"""M97 contracts: preserve authoritative contact, headshots, bounce, and session ownership.

These are source-level contracts; Roblox collision, humanoid animation, and network
replication still require a Studio Play smoke test.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


class CombatRefactorM97Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.attack = source("src/server/combat/AttackService.luau")
        cls.damage = source("src/server/combat/AttackDamageResolver.luau")
        cls.aim = source("src/shared/combat/AttackAimGeometry.luau")
        cls.shared_config = source("src/shared/combat/AttackConfig.luau")
        cls.session = source("src/server/combat/AttackSessionStore.luau")

    def test_attack_service_is_orchestrator_and_delegates_session_state(self):
        for token in (
            'require(CombatShared:WaitForChild("AttackAimGeometry"))',
            'require(script.Parent:WaitForChild("AttackDamageResolver"))',
            'poseEvent.Name = "AttackWeaponPose"',
            'event.Name = "AttackIntent"',
            'AttackSessionStore.Begin(player, character, serial, clientAttackId, now + attackDuration, damageWindow)',
            'AttackSessionStore.HitTargets(player, character, serial, clientAttackId)',
            'AttackSessionStore.SetHeadshotTarget(player, headshotTarget)',
        ):
            self.assertIn(token, self.attack)
        self.assertNotIn('DamageService.Apply(', self.attack)
        self.assertNotIn('EntityHitboxService.QueryDamageablesInBox(', self.attack)

    def test_aim_is_pure_math_with_original_validation_limits(self):
        for token in (
            'function AttackAimGeometry.Normalize(',
            'function AttackAimGeometry.HeadshotSegment(',
            'function AttackAimGeometry.InterpolateDirection(',
            'or not finiteVector(aimOrigin)',
            'or not finiteVector(aimDirection)',
            'Config.HeadshotAimOriginMaxDistance',
            'if magnitude <= 1e-6 then',
            'math.max(0, (rootPosition - origin):Dot(direction))',
            'previous:Lerp(current, alpha)',
        ):
            self.assertIn(token, self.aim)
        for unwanted in ('Workspace', 'Players', 'OnServerEvent', 'task.spawn', 'Heartbeat'):
            self.assertNotIn(unwanted, self.aim)

    def test_hitbox_contact_independent_of_aim_and_multi_target(self):
        query = 'EntityHitboxService.QueryDamageablesInBox(character, boxCFrame, boxSize, hitTargets)'
        aim = 'EntityHitboxService.RaycastAimRegions(character, rayStart, rayDirection, attackRange)'
        self.assertIn(query, self.damage)
        self.assertIn(aim, self.damage)
        self.assertLess(self.damage.index(query), self.damage.index(aim))
        self.assertIn('for _, target in ipairs(contacts) do', self.damage)
        self.assertIn('and (not hitTargets or hitTargets[model] ~= true)', self.damage)
        self.assertIn('hitTargets[model] = true', self.damage)
        self.assertIn('hitCount += 1', self.damage)
        self.assertNotIn('break', self.damage)

    def test_only_one_headshot_per_attack_and_state_returned(self):
        self.assertIn('if #contacts > 0 and headshotTarget == nil then', self.damage)
        self.assertIn('local isHeadshot = headshotTarget == nil', self.damage)
        self.assertIn('and aimedRegion.zone == "head"', self.damage)
        self.assertIn('and aimedRegion.model == model', self.damage)
        self.assertIn('headshotTarget = model', self.damage)
        self.assertIn('return hitCount, headshotTarget', self.damage)
        self.assertIn('headshotTarget = AttackSessionStore.HeadshotTarget(player)', self.attack)

    def test_hit_effects_damage_and_attributes_not_lost(self):
        for token in (
            'DamageService.Apply(character, model, rawDamage, isHeadshot)',
            'HitEffectService.Publish(character, model, model:GetAttribute("LastCritical") == true, hitPosition)',
            'SetAttribute("LastHeadshot", isHeadshot)',
            'SetAttribute("LastAttackHeadshot", true)',
            'SetAttribute("LastAttackHitZone", "body")',
            'Config.HeadshotDamageMultiplier',
            '[game1][attack] hit',
        ):
            self.assertIn(token, self.damage)

    def test_environment_contact_and_bounce_before_damage(self):
        sweep = self.attack.split('local function applyAnimatedWeaponSweep(', 1)[1].split('local function clearAttackState(', 1)[0]
        query = 'WeaponEnvironmentCollision.Query(previousVolume, volume)'
        policy = 'HostilePursuitRegistry.Count(character)'
        bounce = 'triggerWeaponBounce('
        damage = 'hitCount += applyDamageInVolume('
        for token in (query, policy, bounce, damage):
            self.assertIn(token, sweep)
        self.assertLess(sweep.index(query), sweep.index(policy))
        self.assertLess(sweep.index(policy), sweep.index(bounce))
        self.assertLess(sweep.index(bounce), sweep.index(damage))
        self.assertIn('if character:GetAttribute("InCombat") == true or pursuerCount > 0 then', sweep)

    def test_pose_guard_and_authored_damage_window_stay_server_side(self):
        for token in (
            'elapsed + 1e-4 < damageWindow.startTime',
            'elapsed > damageWindow.endTime + 1e-4',
            'Config.WeaponPoseValidationSlack',
            'session.clientAttackId ~= clientAttackId',
            'session.character ~= character',
            'WeaponAttackVolume.ReadWeaponBox(weapon)',
            'WeaponAttackVolume.Build(',
            'AttackAimGeometry.Normalize(root.Position, payload.aimOrigin, payload.aimDirection)',
        ):
            self.assertIn(token, self.attack)


if __name__ == '__main__':
    unittest.main()
