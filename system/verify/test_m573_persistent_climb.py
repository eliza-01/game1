"""Kinematic lift control (supersedes M573 pulses), not an engine-physics acceptance test."""
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'src/server/monster'


class PersistentClimb(unittest.TestCase):
    def test_execute_climb_controller(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua:
            self.skipTest('Standalone Lua interpreter unavailable')
        proc = subprocess.run([lua, str(ROOT/'system/verify/climb_pulses_m573.lua'),
                               str(BASE/'MonsterClimbMotion.luau')], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout+proc.stderr)

    def test_no_jump_or_collision_override_and_retry_ownership(self):
        climb = (BASE/'MonsterClimbMotion.luau').read_text()
        nav = (BASE/'MonsterExperimentalNavigation.luau').read_text()
        self.assertIn('root.Anchored=true', climb)
        self.assertIn('root.CFrame=root.CFrame+delta.Unit*allowed', climb)
        self.assertNotIn('LinearVelocity")', climb)
        self.assertEqual(climb.count('Workspace:Blockcast('), 1)
        for forbidden in ('PivotTo(', 'CanCollide=', 'ChangeState(', 'JumpHeight=', 'task.spawn(', 'deadline='):
            self.assertNotIn(forbidden, climb)
        self.assertIn('if result=="Failed" then waitRetry(agent,state,now,"ClimbFailed")', nav)
        self.assertIn('local failed=(state.climb and state.climb.landing)', nav)
        self.assertIn('if (not lower or lower.Distance>radius+2) and directClear', nav)
        self.assertIn('Navigation.Clear(agent); agent.humanoid:Move(Vector3.zero,false)', nav)
