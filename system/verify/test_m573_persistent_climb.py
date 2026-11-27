"""Ballistic jump control (supersedes M575 lift), not an engine-physics acceptance test."""
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

    def test_no_kinematic_or_collision_override_and_retry_ownership(self):
        climb = (BASE/'MonsterClimbMotion.luau').read_text()
        nav = (BASE/'MonsterExperimentalNavigation.luau').read_text()
        self.assertIn('root:ApplyImpulse(delta*root.AssemblyMass)', climb)
        self.assertIn('agent.humanoid.WalkSpeed=speed', climb)
        for forbidden in ('root.Anchored=', 'root.CFrame=', 'LinearVelocity")', 'Blockcast(', 'PivotTo(', 'CanCollide=', 'JumpHeight=', 'task.spawn(', 'deadline='):
            self.assertNotIn(forbidden, climb)
        self.assertIn('if result=="Failed" then waitRetry(agent,state,now,"ClimbFailed")', nav)
        self.assertIn('local failed=(state.climb and state.climb.landing)', nav)
        self.assertIn('if (not lower or lower.Distance>radius+2) and directClear', nav)
        self.assertIn('Navigation.Clear(agent); agent.humanoid:Move(Vector3.zero,false)', nav)
