"""Fence regression: execute geometry against mocked spatial-query hits.
Actual Roblox physical climbing still requires Studio Play.
"""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'src/server/monster'


class MeleeObstacleRecovery(unittest.TestCase):
    def test_shared_start_hit_and_attack_pursuit(self):
        policy = (BASE / 'MonsterTargetPolicy.luau').read_text()
        self.assertIn('and meleeObstacleClear(agent, target)', policy)
        self.assertIn('return withinAttackRange(agent, target) and hasLineOfSight(agent, target)', policy)
        self.assertIn('return hasLineOfSight(agent, target)', policy)
        self.assertIn('state.climb ~= nil', policy)
        self.assertIn('if isRecovering(agent) then return false end', policy)
        self.assertIn('== "ranged" then return true', policy)
        ai = (BASE / 'MonsterAIService.luau').read_text()
        self.assertIn('Navigation.Enabled(agent) or not Retreat.IsRanged(agent.model)', ai)
        self.assertIn('((not Navigation.Enabled(agent) and Retreat.IsRanged(agent.model)) or TargetPolicy.CanBeginTargetedCast(agent,attacker))', ai)
        self.assertIn('not TargetPolicy.CanBeginTargetedCast(agent,target) then\n            action = "Chase"', ai)
        executor = (BASE / 'MonsterAttackExecutor.luau').read_text()
        self.assertIn('clear = TargetPolicy.MeleeObstacleClear(agent, target)', executor)
        self.assertIn('nextObstacleCheck = now + .2', executor)
        self.assertLess(executor.index('TargetPolicy.AttackStillConnects(agent, target)'), executor.index('DamageService.Apply('))

    def test_return_and_navigation_diagnostics(self):
        ai = (BASE / 'MonsterAIService.luau').read_text()
        self.assertLess(ai.index('SetAttribute("MonsterLastReturnRecoveryMode"'), ai.index('stopNavigation(agent)', ai.index('local function beginReturn')))
        for reason in ('MonsterOutsideHomeLeash', 'TargetOutsideHomeLeash', 'NoDamageTimeout', 'TargetLost', 'TargetOutsideTerritoryOrIsolation'):
            self.assertIn(reason, ai)
        self.assertIn('HomeLeash.NoDamageTimeout(agent.lastDamageAt, now, GameOptions.HostileNoDamageReturnSeconds())', ai)
        nav = (BASE / 'MonsterExperimentalNavigation.luau').read_text()
        self.assertIn('if state.index~=previousIndex then resetSample(agent,state,now); state.moveAt=0 end', nav)
        for event in ('RouteComplete', 'DirectPathClear', 'RouteSegmentStuck', 'ClimbFailed', 'PointOutsidePursuitBoundary'):
            self.assertIn(event, nav)

    def test_geometry_thin_fence_and_wall(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua:
            self.skipTest('Standalone Lua interpreter not installed')
        source = (BASE / 'MonsterRecoveryGeometry.luau').read_text()
        # Translate the one Luau if-expression; the remaining geometry is Lua.
        source = source.replace('if visual and visual:IsA("BasePart") then visual.Position.Y+visual.Size.Y/2 else root.Position.Y+root.Size.Y/2', '(visual and visual:IsA("BasePart")) and (visual.Position.Y+visual.Size.Y/2) or (root.Position.Y+root.Size.Y/2)')
        with tempfile.TemporaryDirectory() as tmp:
            module = Path(tmp) / 'geometry.lua'
            module.write_text(source)
            subprocess.run([lua, str(ROOT/'system/verify/melee_obstacle_m563.lua'), str(module)], check=True, capture_output=True, text=True)


if __name__ == '__main__':
    unittest.main()
