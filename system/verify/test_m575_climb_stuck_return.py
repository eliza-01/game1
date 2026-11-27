import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'src/server/monster'
sys.path.insert(0,str(ROOT/'system/control-center'))
from options_store import normalize_monster_ai

class ClimbStuckReturn(unittest.TestCase):
    def test_watchdog_runtime(self):
        lua=shutil.which('texlua') or shutil.which('lua')
        if not lua: self.skipTest('Standalone Lua interpreter unavailable')
        p=subprocess.run([lua,str(ROOT/'system/verify/stuck_watchdog_m575.lua'),str(BASE/'MonsterStuckWatchdog.luau')],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)

    def test_config_migration_and_validation(self):
        old={'noDamageReturnSeconds':88,'experimentalNavigation':{'climbSpeed':7}}
        self.assertEqual(normalize_monster_ai({},old)['experimentalNavigation']['stuckReturnSeconds'],30)
        out=normalize_monster_ai({'experimentalNavigation':{'stuckReturnSeconds':45}},old)
        self.assertEqual(out['noDamageReturnSeconds'],88)
        self.assertNotIn('climbSpeed',out['experimentalNavigation'])
        self.assertEqual(out['experimentalNavigation']['stuckReturnSeconds'],45)
        for val in (0,301,True,float('nan')):
            with self.assertRaises(ValueError): normalize_monster_ai({'experimentalNavigation':{'stuckReturnSeconds':val}},old)
        self.assertIn('stuckReturnSeconds = math.clamp(finite(source.stuckReturnSeconds, 30)',(ROOT/'src/shared/GameOptions.luau').read_text())
        self.assertIn('stuckReturnSeconds:30',(ROOT/'system/control-center/static/options.js').read_text())
        self.assertIn('id="option-nav-stuckReturnSeconds"',(ROOT/'system/control-center/static/index.html').read_text())

    def test_return_owned_by_ai_and_not_plan(self):
        nav=(BASE/'MonsterExperimentalNavigation.luau').read_text()
        self.assertIn('if not agent.returning then\n        local expired,seconds=Watchdog.Step',nav)
        self.assertNotIn('stuckWatchdog',nav.split('local function clearPlan',1)[1].split('function Navigation.Clear',1)[0])
        ai=(BASE/'MonsterAIService.luau').read_text()
        self.assertEqual(ai.count('beginReturn(agent, "StuckTimeout")'),2)
        self.assertIn('return Experimental.NavigateTo',(BASE/'MonsterNavigationDispatch.luau').read_text())
        climb=(BASE/'MonsterClimbMotion.luau').read_text()
        self.assertIn('root:ApplyImpulse(',climb)
        self.assertIn('CharacterConfig.JumpVelocity*math.sqrt(JumpSettings.heightMultiplier)',climb)
        self.assertNotIn('root.Anchored=',climb)
        self.assertNotIn('root.CFrame=',climb)
