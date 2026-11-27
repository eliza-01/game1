"""M561 contracts and actual deterministic route-store/graph math tests.
Studio Play is still required for physical climbing and spatial queries.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'system/control-center'))
from options_store import normalize_monster_ai
from rescue_route_store import snapshot,sync


def read(path): return (ROOT/path).read_text(encoding='utf-8-sig')


class NavigationM561(unittest.TestCase):
    def test_graph_algorithm(self):
        lua=shutil.which('texlua') or shutil.which('lua')
        if not lua: self.skipTest('Standalone Lua interpreter not installed; graph test can run separately')
        subprocess.run([lua,str(ROOT/'system/verify/rescue_graph_m561.lua'),str(ROOT/'src/server/monster/MonsterRescueGraph.luau')],check=True,capture_output=True,text=True)

    def test_procedural_routes_no_manual_junction(self):
        plugin=read("system/studio-plugin/modules/StudioRescueRoutes.luau")
        self.assertNotIn("snapPoint",plugin)
        self.assertNotIn("Junction",plugin)
        self.assertIn("local p=mouse.Hit.Position",plugin)

    def test_options_merge_without_losing_return_timer(self):
        data=normalize_monster_ai({'experimentalNavigation':{'stuckPercent':40}}, {'noDamageReturnSeconds':88,'experimentalNavigation':{'climbSpeed':7}})
        self.assertEqual(data['noDamageReturnSeconds'],88)
        self.assertNotIn('climbSpeed',data['experimentalNavigation'])
        self.assertEqual(data['experimentalNavigation']['stuckPercent'],40)
        for value in (0,91,float('nan'),True):
            with self.assertRaises(ValueError): normalize_monster_ai({'experimentalNavigation':{'stuckPercent':value}})

    def test_database_mirror_scoped_and_atomic(self):
        map_id='a'*8+'-'+ 'b'*4+'-'+ 'c'*4+'-'+ 'd'*4+'-'+ 'e'*12
        route_id='Route_'+map_id
        body={'mapId':map_id,'placeId':0,'routes':[{'id':route_id,'points':[[0,0,0],[3,4,0],[3,4,12]]}]}
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(snapshot(tmp)['maps'],{})
            self.assertEqual(sync(tmp,body)['edges'],2)
            self.assertEqual(snapshot(tmp)['maps']['0:'+map_id]['routes'][0]['lengthStuds'],17)
            sync(tmp,{**body,'placeId':22})
            before=snapshot(tmp)
            with self.assertRaises(ValueError): sync(tmp,{**body,'routes':[{'id':route_id,'points':[[0,0,0],[float('inf'),0,0]]}]})
            self.assertEqual(snapshot(tmp),before)
            sync(tmp,{**body,'routes':[]})
            self.assertEqual(snapshot(tmp)['maps']['0:'+map_id]['routes'],[])
            self.assertEqual(len(snapshot(tmp)['maps']['22:'+map_id]['routes']),1)

    def test_experiment_scope_and_cleanup(self):
        base='src/server/monster/'
        dispatch=read(base+'MonsterNavigationDispatch.luau')
        self.assertIn('RunService:IsStudio()',dispatch)
        self.assertIn('MonsterChaseNavigation',dispatch)
        self.assertIn('MonsterExperimentalNavigation',dispatch)
        self.assertIn('Experimental.Clear(agent); Legacy.StopNavigation(agent)',dispatch)
        nav=read(base+'MonsterExperimentalNavigation.luau')
        self.assertIn('(agent.root.Position-state.position).Magnitude',nav)
        self.assertIn('SkillMoveMultiplier',nav)
        self.assertIn('state.expected*Config.stuckPercent/100',nav)
        self.assertIn('route.cost<detour.cost',nav)
        self.assertIn('localCost<=plan.cost',nav)
        self.assertIn('Geometry.RecoveryExitClear',nav)
        self.assertIn('state.failed',nav)
        geometry=read(base+'MonsterRecoveryGeometry.luau')
        self.assertIn('Workspace.Terrain',geometry)
        self.assertIn('RespectCanCollide=true',geometry)
        self.assertIn('Config.searchWidth,.2,Config.searchDistance',geometry)
        self.assertIn('head.Distance-lower.Distance',geometry)
        climb=read(base+'MonsterClimbMotion.luau')
        self.assertIn('root:ApplyImpulse(',climb)
        self.assertNotIn('root.Anchored=',climb)
        self.assertNotIn('CanCollide=',climb)
        self.assertNotIn('PivotTo(',climb)
        ai=read(base+'MonsterAIService.luau')
        self.assertIn('not TargetPolicy.CanBeginTargetedCast(agent,target)',ai)
        self.assertIn('Navigation.Enabled(agent)',ai)

    def test_authoring_separation(self):
        plugin=read('system/studio-plugin/modules/StudioRescueRoutes.luau')
        self.assertIn('RunService:IsRunning()',plugin)
        self.assertIn('Vector3Value',plugin)
        self.assertIn('preview.Archivable=false',plugin)
        self.assertIn('studio-sync',plugin)
        self.assertIn('Sync Database',plugin)
        self.assertIn('Game1RescueRoutes',plugin)
        self.assertIn('rescueRoutes',read('system/control-center/static/game-balance.js'))
        self.assertIn('"/api/rescue-routes/studio-sync"',read('system/control-center/web_server.py'))
