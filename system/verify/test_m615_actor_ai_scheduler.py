"""M615 fixed cadence extraction; hashes protect the M614 decision bodies.
The queue runs as real Lua; physical movement remains a Studio acceptance gate.
"""
from pathlib import Path
import hashlib
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]

def read(path):
    return (ROOT / path).read_text(encoding='utf-8')

def digest(text):
    return hashlib.sha256(text.strip().encode()).hexdigest()

class ActorAISchedulerM615(unittest.TestCase):
    def test_queue_behavior(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua:
            self.skipTest('Lua CLI unavailable')
        subprocess.run([lua, 'system/verify/ai_schedule_m615.lua'], cwd=ROOT, check=True, timeout=15)

    def test_monster_decision_parity(self):
        # M614 runAgent body dedented; continue -> return, terminal break -> return false.
        ai = read('src/server/monster/MonsterAIService.luau')
        body = ai.split('local function stepAgent(agent: any)\n', 1)[1].split('\nend\n\n-- Confirmed damage', 1)[0]
        self.assertEqual(digest(body), 'eada9d31c7fc2505928853056a29b7b4fc9292224d658aaccf2e9220a3680150')
        self.assertIn('Lifecycle.Start(stepAgent, random, THINK_INTERVAL)', ai)
        self.assertIn('TARGET_SCAN_INTERVAL = 0.30', ai)
        self.assertNotIn('task.wait(', ai)

    def test_npc_decision_parity(self):
        ai = read('src/server/npc/NpcCombatAIService.luau')
        body = ai.split('local function tickAgent', 1)[1].split('function NpcCombatAIService.Bind', 1)[0]
        self.assertEqual(digest(body.replace("agent.motion.Set", "agent.presentation.Set")), 'a2af89fd9e79b3aab0f61d8e3c3e0b9124849e0ce0e398e59d424ad38e2cdc5e')
        self.assertIn('Scheduler.Register(agent, TICK_SECONDS, delay, tickAgent, nil, true, if Activity.Enabled then Activity.NpcDelay else nil)', ai)
        self.assertIn('Scheduler.Remove(agent)', ai)
        self.assertEqual(ai.count('RunService.Heartbeat:Connect'), 1)
        self.assertIn('agent.pursuit:Step(targetRoot, agent.attackRadius, maxSpeed)', ai)
        self.assertNotIn('elapsed %= TICK_SECONDS', ai)

    def test_single_owner_and_lifecycle(self):
        lifecycle = read('src/server/monster/MonsterAgentLifecycle.luau')
        self.assertIn('function MonsterAgentLifecycle.Start(stepAgent: (any) -> (), random: Random, thinkInterval: number)', lifecycle)
        self.assertIn('Scheduler.Register(agent, thinkInterval, thinkInterval + random:NextNumber(0, thinkInterval), stepAgent, releaseAgent, nil, if Activity.Enabled then Activity.MonsterDelay else nil)', lifecycle)
        self.assertIn('Scheduler.Remove(agent)', lifecycle)
        self.assertNotIn('runAgent', lifecycle)
        scheduler = read('src/server/actor/ActorAIScheduler.luau')
        self.assertEqual(scheduler.count('RunService.Heartbeat:Connect'), 1)
        for token in ('MoveTo(', 'PathfindingService', 'Raycast(', 'GetPlayers(', 'MonsterNavigation'):
            self.assertNotIn(token, scheduler)

    def test_runtime_tree_and_mechanics(self):
        self.assertIn('"$path": "src/server"', read('default.project.json'))
        catalog = read('system/control-center/mechanics/catalog.py')
        for key in ('actor-ai-scheduler', 'actor-ai-queue'):
            self.assertIn(key, catalog)
            for name in ('monster', 'npc'):
                self.assertIn(key, read('system/control-center/mechanics/' + name + '.py'))
