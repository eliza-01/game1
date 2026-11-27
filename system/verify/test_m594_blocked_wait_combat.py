"""M594: actual fallback/target policy with mocked engine queries; Play remains open."""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'src/server/monster'

class BlockedWaitCombat(unittest.TestCase):
    def test_wait_wake_and_attack_validation(self):
        lua=shutil.which('texlua') or shutil.which('lua')
        if not lua: self.skipTest('Standalone Lua interpreter unavailable')
        policy=(BASE/'MonsterTargetPolicy.luau').read_text()
        # Translate Luau type annotations and two if-expressions only.
        policy=re.sub(r': (?:Model|BasePart|Vector3|number|boolean|any)\??(?=[,\)\s])','',policy)
        policy=policy.replace('return if root and root:IsA("BasePart") then root else nil','return (root and root:IsA("BasePart")) and root or nil')
        policy=policy.replace('return if root and root:IsA("BasePart") then root else rootOf(model)','return (root and root:IsA("BasePart")) and root or rootOf(model)')
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'policy.lua'; p.write_text(policy)
            run=subprocess.run([lua,str(ROOT/'system/verify/blocked_wait_m594.lua'),str(BASE/'MonsterBlockedPursuit.luau'),str(p),str(ROOT/'src/server/actor/ActorTargetRoot.luau')],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)

    def test_damage_wake_wiring_and_single_owner(self):
        ai=(BASE/'MonsterAIService.luau').read_text()
        self.assertIn('Skills.MarkAttacked(agent.model)\n        Navigation.NotifyDamage(agent,attacker)',ai)
        self.assertLess(ai.index('Navigation.NotifyDamage(agent,attacker)'),ai.index('local targetRoot = rootOf(attacker)'))
        self.assertIn('elseif action == "BeginAttack" then\n        stopNavigation(agent)',ai)
        dispatch=(BASE/'MonsterNavigationDispatch.luau').read_text()
        self.assertIn('state.target==attacker and not agent.returning then Blocked.NotifyDamage(state)',dispatch)
        nav=(BASE/'MonsterExperimentalNavigation.luau').read_text()
        self.assertIn('Trace.Event(agent,"BLOCKED_REENGAGE",wakeReason)',nav)
        self.assertIn('clearPlan(agent,state,now); state.reengaging=true; state.stuckWatchdog=nil',nav)
        self.assertIn('if before~="Wait" then',nav)
        self.assertIn('if Target.IsRecovering(agent) then return false end',(BASE/'MonsterSkillCast.luau').read_text())
