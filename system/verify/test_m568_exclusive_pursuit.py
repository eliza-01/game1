"""M568: per-spawn mutually exclusive pursuit modes, without a zone fallback."""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
import test_m560_studio_monster_spawns as spawn_tests

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'src/server/monster'

class PursuitPolicy(unittest.TestCase):
    def test_real_policy_without_zone_and_with_territory(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua:
            self.skipTest('Standalone Lua unavailable')
        def plain(path):
            # Only strip Luau function annotations; run the actual policy body.
            return re.sub(r': (?:CFrame|Vector3|Model|boolean|number\??|any)(?=[,)]|\n)', '', path.read_text())
        with tempfile.TemporaryDirectory() as tmp:
            policy = Path(tmp) / 'policy.lua'; policy.write_text(plain(BASE/'MonsterDeathChasePolicy.luau'))
            leash = Path(tmp) / 'leash.lua'; leash.write_text(plain(ROOT/'src/server/actor/ActorHomeLeash.luau'))
            script = Path(tmp) / 'test.lua'
            script.write_text('''
table.freeze=function(t) return t end
local function v(x,y,z) return {X=x,Y=y,Z=z,kind='Vector3'} end
local frame={kind='CFrame',PointToObjectSpace=function(_,p) return p end}
function typeof(x) return type(x)=='table' and x.kind or type(x) end
local zones={}
local collection={GetTagged=function() return zones end}
local world={}
game={GetService=function(_,n) return n=='CollectionService' and collection or world end}
local parent={WaitForChild=function(_,n) return n end}
parent.Parent={WaitForChild=function() return parent end}; script={Parent=parent}
local L=assert(loadfile(arg[2]))()
require=function(n) assert(n=='ActorHomeLeash'); return L end
local P=assert(loadfile(arg[1]))()
local attrs={MonsterSpawnCenter=v(0,0,0),MonsterHomeRadiusStuds=20}
local m={GetAttribute=function(_,k) return attrs[k] end,SetAttribute=function(_,k,x) attrs[k]=x end}
local a={model=m,spawnCenter=v(0,0,0),homeRadius=20}
P.Configure(m,{},true)
assert(not P.UsesHomeLeash(m) and not P.IsBound(m))
assert(attrs.MonsterPursuitMode=='DeathChase' and attrs.MonsterHomeRadiusStuds==nil)
assert(P.AllowsPursuitPosition(a,v(1000,0,0),.5),'unbound DC cannot reject by radius')
local zone={CFrame=frame,Size=v(1000,100,1000),IsA=function() return true end,IsDescendantOf=function() return true end}
zones={zone}; P.Configure(m,{},true)
assert(P.IsBound(m) and not P.UsesHomeLeash(m))
assert(P.AllowsPursuitPosition(a,v(400,0,0),.5) and not P.AllowsPursuitPosition(a,v(600,0,0)))
zones={zone,zone}; P.Configure(m,{},true)
assert(not P.IsBound(m) and not P.UsesHomeLeash(m) and P.AllowsPursuitPosition(a,v(1000,0,0)))
P.Configure(m,{},false)
assert(P.UsesHomeLeash(m) and not P.IsBound(m))
assert(P.AllowsPursuitPosition(a,v(19,0,0),.5) and not P.AllowsPursuitPosition(a,v(20,0,0),.5))
P.Configure(m,{testOwner=1,testKind='guided'},true)
assert(P.UsesHomeLeash(m),'calibration retains previous policy')
P.Configure(m,{testOwner=1,testKind='zone',testZone=1,testZoneFrame=frame,testZoneSize=v(100,100,100)},true)
assert(P.IsBound(m) and not P.UsesHomeLeash(m))
''')
            proc = subprocess.run([lua,str(script),str(policy),str(leash)],capture_output=True,text=True)
            self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
    def test_all_movement_consumers_use_policy(self):
        ai=(BASE/'MonsterAIService.luau').read_text()
        self.assertIn('if DeathChase.UsesHomeLeash(agent.model) then',ai)
        self.assertLess(ai.index('if DeathChase.UsesHomeLeash(agent.model) then'),ai.index('HomeLeash.NoDamageTimeout('))
        for name in ('MonsterExperimentalNavigation','MonsterRangedRetreat'):
            text=(BASE/(name+'.luau')).read_text()
            self.assertIn('DeathChase.AllowsPursuitPosition(',text)
            self.assertNotIn('HomeLeash.Outside(',text)
        ui=(ROOT/'system/control-center/static/game-balance.js').read_text()
        self.assertIn("['home','Home Leash'],['death','Death Chase']",ui)
        self.assertIn("leash.hidden=draft.deathChase",ui)

class SpawnPursuit(unittest.TestCase):
    setUp = spawn_tests.StudioSpawnTests.setUp
    def test_switch_mode_retains_inactive_radius(self):
        saved=self.store.studio_apply({**self.payload,'deathChase':False,'homeRadiusStuds':67})['record']
        self.assertFalse(saved['deathChase']); self.assertEqual(saved['homeRadiusStuds'],67)
        saved=self.store.studio_apply({**self.payload,'deathChase':True,'expectedUpdatedAtUtc':saved['updatedAtUtc']})['record']
        self.assertTrue(saved['deathChase']); self.assertEqual(saved['homeRadiusStuds'],67)
        saved=self.store.studio_apply({**self.payload,'deathChase':False,'expectedUpdatedAtUtc':saved['updatedAtUtc']})['record']
        self.assertFalse(saved['deathChase']); self.assertEqual(saved['homeRadiusStuds'],67)
        self.assertIn('"homeRadiusStuds":67.0',self.store.registry_path.read_text())
    def test_missing_override_inherits_balance_in_catalog(self):
        saved=self.store.studio_apply(self.payload)['record']
        manifest=self.store._load()
        manifest['records'][saved['spawnId']].pop('deathChase')
        self.store._commit(manifest)
        self.assertEqual(self.store.studio_catalog()['records'][0]['deathChase'],self.toad['deathChase'])
