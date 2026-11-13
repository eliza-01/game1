"""M320 contracts and independently calculated boundary/transition examples.

Roblox Luau calls and client UI require Studio Play; these tests keep the
range, scheduler, and visibility ownership changes pinned in the codebase.
"""
import math
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]


def code(path):
    return (ROOT / path).read_text(encoding="utf-8")


def within(root, point, radius):
    dx, dy, dz = (p - r for r, p in zip(root, point))
    return dx*dx + dz*dz <= (radius + .15)**2 and abs(dy) <= radius + .15


def regen(hp, maximum, elapsed, state="Alive"):
    if state != "Alive" or hp <= 0 or hp >= maximum:
        return hp
    return min(maximum, hp + elapsed*5)


class TestBowRadius(unittest.TestCase):
    def test_release_does_not_lose_range_to_launch_or_camera(self):
        root = (0, 3, 0)
        # At 40 studs from character, regardless of camera/nock positions.
        for camera in ((0, 8, 16), (6, 7, 12), (0, 6, -18)):
            target = (0, 4, -40)
            self.assertTrue(within(root, target, 40))
            camera_to_target = math.dist(camera, target)
            self.assertGreater(camera_to_target, 40) if camera[2] > 0 else None
        self.assertFalse(within(root, (0, 4, -40.5), 40))
        self.assertTrue(within(root, (40, 12, 0), 40))
        range_geometry = code('src/shared/combat/BowRangeGeometry.luau')
        hitscan = code('src/server/combat/BowHitscanService.luau')
        self.assertIn('function Range.Within(root:', range_geometry)
        self.assertIn('delta.X * delta.X + delta.Z * delta.Z', range_geometry)
        self.assertIn('Range.CastDistance(root.Position, origin, range, Policy.MaxDistance)', hitscan)
        self.assertIn('if actor and not Range.Within(root.Position, actor.hitPosition, range)', hitscan)
        self.assertIn('withinRange = Range.Within(root.Position, snapshot.point, bowRange)', hitscan)
        self.assertIn('canReach(character, from, endPoint, target', hitscan)
        self.assertEqual(hitscan.count('DamageService.Apply('), 1)

    def test_loadout_reading_is_live_and_not_synthetic_weapon_only(self):
        service = code('src/server/dev/TestLoadoutService.luau')
        ui = code('src/client/dev/TestLoadoutController.luau')
        self.assertIn('actualAttackRadiusStuds = character and tonumber(character:GetAttribute("AttackRadius"))', service)
        self.assertIn('character:GetAttribute("EquippedWeaponSlug")', service)
        self.assertIn('ActualRuntimeStats', ui)
        self.assertIn('"AttackSpeed", "RunSpeed", "AttackRadius"', ui)
        self.assertIn('character:GetAttribute("AttackRadius")', ui)


class TestHealth(unittest.TestCase):
    def test_regeneration_is_authoritative_rate_and_alive_only(self):
        for hp, delta, expected in ((30, .2, 31), (30, 1, 35), (99.5, 1, 100)):
            self.assertEqual(regen(hp, 100, delta), expected)
        self.assertEqual(regen(40, 100, 1, 'Dying'), 40)
        self.assertEqual(regen(0, 100, 1), 0)
        regen_service = code('src/server/character/CharacterRegenerationService.luau')
        self.assertIn('RunService.Heartbeat:Connect(', regen_service)
        self.assertIn('Players:GetPlayers()', regen_service)
        self.assertIn('character:GetAttribute("LifeState") == "Alive"', regen_service)
        self.assertIn('character:GetAttribute("Damageable") == true', regen_service)
        self.assertIn('Config.RegenerationHPPerSecond * elapsed', regen_service)
        self.assertIn('CharacterRegenerationService', code('src/server/bootstrap/ServiceCatalog.luau'))
        self.assertIn('RegenerationHPPerSecond = 5', code('src/shared/character/CharacterStatsConfig.luau'))

    def test_no_top_hud_and_overhead_visibility_and_tweens(self):
        self.assertFalse((ROOT / 'src/client/character/PlayerStatusController.luau').exists())
        self.assertIn('OverheadHealthController.Start()', code('src/client/init.client.luau'))
        controller = code('src/client/combat/OverheadHealthController.luau')
        self.assertIn('hp < maxHP - 0.001', controller)
        self.assertIn('character:GetAttribute("InCombat") == true', controller)
        self.assertIn('model:GetAttribute("MonsterTargetUserId") == player.UserId', controller)
        self.assertIn('model == aimedMonster', controller)
        self.assertIn('model:GetAttribute("LifeState") == "Alive"', controller)
        view = code('src/client/combat/HealthBarView.luau')
        for token in ('TweenService:Create(fill, TWEEN, goal)', 'ratio <= 0.30', 'ratio <= 0.65',
                      'Instance.new("UICorner")', 'BillboardGui', 'Gui.Enabled'):
            if token == 'Gui.Enabled':
                self.assertIn('gui.Enabled = value and currentStyle[layout].enabled == true', view)
            else:
                self.assertIn(token, view)
        self.assertNotIn('SetAttribute("HP"', controller)
        self.assertNotIn('SetAttribute("HP"', view)


class TestMonsterResponse(unittest.TestCase):
    def test_direct_damage_signal_not_proximity_timer(self):
        ai = code('src/server/monster/MonsterAIService.luau')
        self.assertIn('DamageSignals.Event:Connect(onDamaged)', ai)
        self.assertIn('CombatState.Enter(agent, attacker)', ai)
        self.assertIn('agent.retaliating = true', ai)
        self.assertIn('if not aggressive(agent) and not agent.retaliating', ai)
        self.assertIn('AttackExecutor.Begin(agent, attacker', ai)
        self.assertIn('navigateTo(agent, targetRoot.Position, runSpeedStuds(agent))', ai)
        self.assertIn('if attempted <= 0 or killed', ai)
        self.assertIn('function MonsterAgentLifecycle.Find(model:', code('src/server/monster/MonsterAgentLifecycle.luau'))
        self.assertIn('ActorDamageSignals.Publish(attacker, target', code('src/server/combat/DamageService.luau'))


if __name__ == '__main__':
    unittest.main()
