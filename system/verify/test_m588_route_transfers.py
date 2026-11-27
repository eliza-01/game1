"""Integration contracts for the M588 navigation changes; graph math is exercised by M561 Lua scenarios."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def read(name):
    return (ROOT / 'src/server/monster' / (name + '.luau')).read_text(encoding='utf-8-sig')

class RouteTransfersM588(unittest.TestCase):
    def test_startup_and_transfer_collision_contract(self):
        self.assertIn('Navigation.Prepare()', read('MonsterAIService'))
        self.assertIn('Experimental.Initialize()', read('MonsterNavigationDispatch'))
        self.assertIn('Navigation.Initialize=Graph.Initialize', read('MonsterExperimentalNavigation'))
        self.assertIn('function(a,b) return Geometry.RouteEntryClear(a,b,ray) end', read('MonsterExperimentalNavigation'))
        self.assertIn('Queries.Transfer(ctx,link.edge)', read('MonsterRescuePaths'))
        self.assertNotIn('CONNECTION_DISTANCE', read('MonsterRescueTopology'))

    def test_no_periodic_full_search_after_no_plan(self):
        nav = read('MonsterExperimentalNavigation')
        self.assertIn('state.noAccessiblePlan=reason=="NoAccessiblePlan"', nav)
        retry = nav.split('if state.mode=="Retry" then', 1)[1].split('local point=goal', 1)[0]
        guard = retry.split('if state.noAccessiblePlan then', 1)[1].split('end', 1)[0]
        self.assertIn('return', guard)
        self.assertLess(retry.index('if state.noAccessiblePlan then'), retry.index('choosePlan('))
        self.assertIn('directClear(', retry)
        self.assertIn('state.noAccessiblePlan=nil', nav)
        self.assertIn('Watchdog.Step(', nav)
