"""Solid wall regression; engine physics still needs Studio."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'src/server/monster'


class BoundedObstacleDetour(unittest.TestCase):
    def test_solid_wall_two_corner_route(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua:
            self.skipTest('Standalone Lua interpreter unavailable')
        source = (BASE / 'MonsterRecoveryGeometry.luau').read_text()
        source = source.replace('if visual and visual:IsA("BasePart") then visual.Position.Y+visual.Size.Y/2 else root.Position.Y+root.Size.Y/2', '(visual and visual:IsA("BasePart")) and (visual.Position.Y+visual.Size.Y/2) or (root.Position.Y+root.Size.Y/2)')
        with tempfile.TemporaryDirectory() as tmp:
            module = Path(tmp) / 'geometry.lua'
            module.write_text(source)
            nav = Path(tmp) / 'navigation.lua'
            nav.write_text((BASE/'MonsterExperimentalNavigation.luau').read_text()
                           .replace('state.index+=1','state.index=state.index+1')
                           .replace('state.expected+=','state.expected=state.expected+')
                           .replace('if state.plan then point else nil','state.plan and point or nil'))
            proc = subprocess.run([lua, str(ROOT/'system/verify/obstacle_detour_m564.lua'), str(module), str(nav), str(BASE/'MonsterStuckWatchdog.luau')], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stdout+proc.stderr)

    def test_retry_replans_without_recharging_wall(self):
        nav = (BASE / 'MonsterExperimentalNavigation.luau').read_text()
        retry = nav.split('if state.mode=="Retry" then',1)[1].split('local point=goal',1)[0]
        self.assertIn('directClear(agent,foot,goal,height,ray)', retry)
        self.assertIn('choosePlan(agent,state,foot,goal', retry)
        self.assertIn('if state.climb or not state.plan then return end', retry)
        self.assertNotIn('move(agent', retry)
        self.assertIn('"NoAccessiblePlan"', nav)
        self.assertIn('MonsterRecoveryActualSpeed', nav)
        self.assertIn('MonsterRecoveryExpectedSpeed', nav)
        dispatch = (BASE / 'MonsterNavigationDispatch.luau').read_text()
        self.assertIn('MonsterNavigationBackend', dispatch)
        ai = (BASE / 'MonsterAIService.luau').read_text()
        self.assertIn('agent.recoveryNavigation.mode=="Retry" then\n        Presentation.PlayCombatIdle(agent)', ai)


if __name__ == '__main__':
    unittest.main()
