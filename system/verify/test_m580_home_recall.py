import shutil
import subprocess
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'src/server/monster'

class HomeRecall(unittest.TestCase):
    def test_phase_machine(self):
        lua=shutil.which('texlua') or shutil.which('lua')
        if not lua: self.skipTest('Standalone Lua interpreter unavailable')
        result=subprocess.run([lua,str(ROOT/'system/verify/home_recall_m580.lua'),str(BASE/'MonsterHomeRecall.luau')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_runtime_wiring(self):
        ai=(BASE/'MonsterAIService.luau').read_text()
        life=(BASE/'MonsterAgentLifecycle.luau').read_text()
        nav=(BASE/'MonsterExperimentalNavigation.luau').read_text()
        self.assertIn('if reason == "StuckTimeout" then',ai)
        self.assertIn('if HomeRecall.Step(agent) then leaveCombat(agent) end',ai)
        self.assertIn('or HomeRecall.Active(agent) or',ai)
        self.assertEqual(life.count('HomeRecall.Cancel(agent)'),2)
        self.assertIn('elseif result=="Timeout" then',nav)
        self.assertIn('clearPlan(agent,state,now); state.nextCheck=now',nav)
        self.assertIn('HomeRecall.Start()',ai)
        self.assertIn('MonsterHomeRecallVisual', (BASE/'MonsterHomeRecall.luau').read_text())
        self.assertIn('MonsterHomeRecallVisual', (ROOT/'src/client/monster/MonsterHomeRecallVisuals.luau').read_text())
        self.assertIn('Aura.PlayAt(', (ROOT/'src/client/monster/MonsterHomeRecallVisuals.luau').read_text())
        self.assertIn('MonsterHomeRecallVisuals")).Start()', (ROOT/'src/client/init.client.luau').read_text())
