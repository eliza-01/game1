"""M567: diagnostic output is opt-in and wraps the actual ray, not a second ray."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'src/server/monster'

class NavigationTrace(unittest.TestCase):
    def test_real_trace_module(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua:
            self.skipTest('Standalone Lua interpreter unavailable')
        source = (BASE / 'MonsterNavigationTrace.luau').read_text().replace('serial+=1', 'serial=serial+1')
        with tempfile.TemporaryDirectory() as tmp:
            module = Path(tmp) / 'trace.lua'
            module.write_text(source)
            script = Path(tmp) / 'test.lua'
            script.write_text('''
local attrs,logs={},{}
local workspace={GetAttribute=function(_,key) return attrs[key] end}
game={GetService=function(_,name) if name=='Workspace' then return workspace end return {IsStudio=function() return true end} end}
table.freeze=function(t) return t end
print=function(...) logs[#logs+1]=table.concat({...},' ') end
local T=assert(loadfile(arg[1]))()
local agent={model={Name='Toad'}}
local other={model={Name='Wolf'}}
local params={CollisionGroup='Bodies'}
local mt={__add=function(a,b) return {X=a.X+b.X,Y=a.Y+b.Y,Z=a.Z+b.Z} end}
local a=setmetatable({X=1,Y=2,Z=3},mt)
local d={X=3,Y=0,Z=0,Magnitude=3}
T.Bind(params,agent); T.Ray(params,'PRIMARY_HEAD',a,d,nil); T.Event(agent,'TEST')
assert(#logs==0,'disabled trace must emit nothing')
attrs.Game1MonsterNavTrace=true; attrs.Game1MonsterNavTraceFilter='Toad'
T.Bind(params,agent); T.Ray(params,'PRIMARY_HEAD',a,d,{Instance={GetFullName=function() return 'Workspace.Wall' end},Position={X=2,Y=2,Z=3},Distance=1})
assert(#logs==1 and logs[1]:find('from=(1.00,2.00,3.00)',1,true) and logs[1]:find('hit=Workspace.Wall',1,true))
T.Changed(agent,'MODE','Direct'); T.Changed(agent,'MODE','Direct'); T.Changed(agent,'MODE','Retry')
T.Event(other,'TEST'); assert(#logs==3,'filter and dedup')
T.Rate(agent,'MOVE',1,'one'); T.Rate(agent,'MOVE',1,'two'); assert(#logs==4,'rate limit')
attrs.Game1MonsterNavTrace=false; T.Event(agent,'TEST'); T.Ray(params,'PRIMARY_HEAD',a,d,nil); assert(#logs==4,'live disable')
assert(T.RouteObserver(agent,a,a,40)==nil)
attrs.Game1MonsterNavTrace=true
assert(T.RouteObserver(agent,a,a,40)==nil,'detail trace defaults off')
attrs.Game1MonsterNavRouteTrace=true
assert(T.RouteObserver(other,a,a,40)==nil,'actor filter applies')
local start=setmetatable({X=1,Y=2,Z=3},{__sub=function(a,b) return {Magnitude=10} end})
local observe=T.RouteObserver(agent,start,a,80)
assert(observe and logs[5]:find('searchRadius=80.00 exitLimit=10.00',1,true))
observe('GRAPH_ENTRY',{id=7,sources={['routeA:1-2']=true}},a,3,'FootBlocked',{Instance={GetFullName=function() return 'Workspace.Fence' end},Position=a},true)
assert(logs[6]:find('route=routeA:1-2',1,true) and logs[6]:find('reason=FootBlocked',1,true) and logs[6]:find('hit=Workspace.Fence',1,true) and logs[6]:find('cached=true',1,true))
''')
            proc = subprocess.run([lua, str(script), str(module)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_ray_wrapper_uses_one_query_and_preserves_result(self):
        geometry = (BASE / 'MonsterRecoveryGeometry.luau').read_text()
        wrapper = geometry.split('local function tracedRay',1)[1].split('function Geometry.Body',1)[0]
        self.assertEqual(wrapper.count('Workspace:Raycast('), 1)
        self.assertIn('Trace.Ray(params,label,origin,delta,result)', wrapper)
        self.assertIn('return result', wrapper)
        for label in ('PRIMARY_HEAD','PROBE_HEAD','PROBE_FOOT','HEEL_RAY'):
            self.assertIn('tracedRay("'+label+'"', geometry)

if __name__ == '__main__':
    unittest.main()
