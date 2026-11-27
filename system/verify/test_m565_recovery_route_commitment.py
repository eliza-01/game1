"""Regression: a route is not interrupted by a combat transition or an unverified exit."""
import unittest
from pathlib import Path
BASE = Path(__file__).resolve().parents[2] / 'src/server/monster'

class RouteCommitment(unittest.TestCase):
    def test_recovery_owns_movement_until_exit(self):
        policy = (BASE / 'MonsterTargetPolicy.luau').read_text()
        self.assertIn('state.plan ~= nil or state.climb ~= nil or state.mode == "Retry"', policy)
        start = policy.split('local function canBeginTargetedCast',1)[1].split('local function attackStillConnects',1)[0]
        self.assertIn('if isRecovering(agent) then return false end', start)
        cast = (BASE / 'MonsterSkillCast.luau').read_text()
        self.assertLess(cast.index('if Target.IsRecovering(agent) then return false end'),cast.index('Navigation.StopNavigation(agent)'))
        nav = (BASE / 'MonsterExperimentalNavigation.luau').read_text()
        self.assertIn('Geometry.RecoveryExitClear(foot,height,goal,ray)', nav)
        geometry = (BASE / 'MonsterRecoveryGeometry.luau').read_text()
        self.assertIn('Geometry.HeadClear(foot,height,goal+UP*.1,params)', geometry)
        self.assertIn('and Geometry.HeadObstacle(foot,height,goal,horizontal(goal-foot).Magnitude,params)==nil', geometry)
        self.assertNotIn('state.exitClearCount', nav)
        self.assertNotIn('state.index>1', nav)
        self.assertIn('"RouteExitBlocked"', nav)
        self.assertIn('"ExternalNavigationStop"', nav)
