"""Blocked chase policy and Options round trip; engine physics still needs Studio."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'src/server/monster'
sys.path.insert(0,str(ROOT/'system/control-center'))
from options_store import OptionsStore, normalize_monster_ai

class BlockedPursuitM591(unittest.TestCase):
    def test_policy_speed_and_geometry(self):
        lua=shutil.which('texlua') or shutil.which('lua')
        if not lua: self.skipTest('Standalone Lua interpreter unavailable')
        modules=['MonsterBlockedPursuit','MonsterNavigationSpeed','MonsterBlockedRetreatGeometry']
        run=subprocess.run([lua,str(ROOT/'system/verify/blocked_pursuit_m591.lua'),*[str(BASE/(m+'.luau')) for m in modules]],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)

    def test_options_round_trip(self):
        defaults={'blockedRetreatBuffer':2,'blockedRetreatSpeedMultiplier':1,'blockedReengageSpeedMultiplier':1.5,'rescueRouteSpeedMultiplier':1.5}
        new={'blockedRetreatBuffer':3,'blockedRetreatSpeedMultiplier':1.2,'blockedReengageSpeedMultiplier':1.8,'rescueRouteSpeedMultiplier':2}
        old={'noDamageReturnSeconds':50,'experimentalNavigation':{'routeConnectionHeight':4,'searchDistance':80}}
        result=normalize_monster_ai({},old)
        for key,value in defaults.items():
            self.assertEqual(result['experimentalNavigation'][key],value)
            for bad in (-1,True,float('nan'),1000):
                with self.subTest(key=key,bad=bad),self.assertRaises(ValueError):
                    normalize_monster_ai({'experimentalNavigation':{key:bad}},old)
            self.assertIn(f'id="option-nav-{key}"',(ROOT/'system/control-center/static/index.html').read_text())
            self.assertIn(f'{key}:{value}',(ROOT/'system/control-center/static/options.js').read_text())
            self.assertIn(f'finite(source.{key}, {value})',(ROOT/'src/shared/GameOptions.luau').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            store=OptionsStore(Path(tmp))
            store.update({'monsterAi':old})
            store.update({'monsterAi':{'experimentalNavigation':new}})
            actual=OptionsStore(Path(tmp)).snapshot()['monsterAi']
            self.assertEqual(actual['noDamageReturnSeconds'],50)
            self.assertEqual(actual['experimentalNavigation']['routeConnectionHeight'],4)
            for key,value in new.items():
                self.assertEqual(actual['experimentalNavigation'][key],value)
                self.assertIn(f'{key} = {value},',store.registry_path.read_text())

    def test_ai_and_mechanics_contract(self):
        ai=(BASE/'MonsterAIService.luau').read_text()
        self.assertIn('not Navigation.IsBlockedRetreating(agent) and HomeLeash.NoDamageTimeout',ai)
        self.assertIn('Navigation.PresentationMultiplier(agent)',ai)
        self.assertIn('state.blockedPursuit ~= nil',(BASE/'MonsterTargetPolicy.luau').read_text())
        docs=(ROOT/'system/control-center/mechanics/monster.py').read_text()
        for phrase in ('Blocked Pursuit · отступление M591','MonsterBlockedPursuit','BlockedWait','Rescue Route speed'):
            self.assertIn(phrase,docs)
