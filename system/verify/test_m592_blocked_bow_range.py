"""Blocked retreat uses the database bow range, never the equipped melee radius."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'src/server/monster'


class BlockedBowRange(unittest.TestCase):
    def test_config_uses_database_bow_radii_and_combat_caps(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua:
            self.skipTest('Standalone Lua interpreter unavailable')
        harness = '''
local node={WaitForChild=function(_,name) return name end}
game={GetService=function() return {WaitForChild=function() return node end} end}
table.clone=function(t) local out={} for k,v in pairs(t) do out[k]=v end return out end
table.freeze=function(t) return t end
math.clamp=function(v,a,b) return math.max(a,math.min(v,b)) end
local balance={Weapons={{type="sword",radius=500},{type="bow",radius=40},{type="bow",radius=50}}}
local bow={MaxDistance=420}
local attack={MaxAimDistance=420}
local modules={GameOptions={ExperimentalMonsterNavigation=function() return {blockedRetreatBuffer=2} end},
  BowProjectileConfig=bow,AttackConfig=attack,Balance=balance}
node.WaitForChild=function(_,name) if name=="combat" or name=="balance" then return node end return name end
require=function(n) return assert(modules[n],n) end
local load=assert(loadfile(arg[1]))
assert(load().bowRange==50)
balance.Weapons[3].radius=1000
assert(load().bowRange==420)
attack.MaxAimDistance=60
assert(load().bowRange==60)
balance.Weapons[3]=nil
local config=load()
assert(config.bowRange==40 and config.blockedRetreatBuffer==2)
'''
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / 'config.lua'
            script.write_text(harness)
            run = subprocess.run([lua,str(script),str(BASE/'MonsterNavigationConfig.luau')],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)

    def test_blocked_step_independent_of_equipment(self):
        source=(BASE/'MonsterExperimentalNavigation.luau').read_text()
        blocked=source.split('local function stepBlocked(',1)[1].split('local before=',1)[0]
        self.assertIn('local range=Config.bowRange',blocked)
        self.assertNotIn('GetAttribute',blocked)
        self.assertNotIn('defaultAttackRadius',source)
        self.assertNotIn('bowMaxDistance',source)
