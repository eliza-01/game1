"""M105 Monster AI agent lifecycle ownership contracts.

Tests are source-level; Roblox event scheduling / spawned instance teardown
needs verification in Studio. This suite also protects the old attack+chase paths.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2] / 'src/server/monster'

def read(name):
    return (ROOT / name).read_text(encoding='utf-8-sig')

class MonsterAgentLifecycleM105(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ai = read('MonsterAIService.luau')
        cls.lifecycle = read('MonsterAgentLifecycle.luau')
        cls.nav = read('MonsterChaseNavigation.luau')
        cls.attack = read('MonsterAttackExecutor.luau')

    def test_coordinator_is_decision_only(self):
        self.assertIn('require(script.Parent:WaitForChild("MonsterAgentLifecycle"))', self.ai)
        self.assertIn('Lifecycle.Start(runAgent, random)', self.ai)
        self.assertIn('Lifecycle.Release(agent)', self.ai)
        for forbidden in ('Workspace.ChildAdded:Connect(', 'model.Destroying:Connect(',
                          'GetAttributeChangedSignal("LifeState")', 'Presentation.LoadTrack(',
                          'local agents:', 'local function bindMonster(', 'MonsterSlug'):
            self.assertNotIn(forbidden, self.ai)
        self.assertIn('AttackExecutor.Begin(agent, target, AttackMovement, random)', self.ai)
        self.assertIn('navigateTo(agent, targetRoot.Position, runSpeedStuds(agent))', self.ai)

    def test_explicit_readiness_and_single_pending_registration(self):
        for required in ('if agents[model] or pending[model] then return end',
                         'pending[model] = true', 'pending[model] = nil',
                         'model:GetAttribute("Game1MonsterRuntime")',
                         'model:IsDescendantOf(Workspace)',
                         'model:WaitForChild("HumanoidRootPart", 5)',
                         'model:WaitForChild("Humanoid", 5)'):
            self.assertIn(required, self.lifecycle)
        self.assertLess(self.lifecycle.index('Navigation.Initialize(agent)'),
                        self.lifecycle.index('agents[model] = agent'))
        self.assertLess(self.lifecycle.index('agents[model] = agent'),
                        self.lifecycle.index('xpcall(runAgent, debug.traceback, agent)'))

    def test_lifecycle_registers_and_disconnects_model_signals(self):
        for signal in ('GetAttributeChangedSignal("LifeState")', 'model.Destroying:Connect(',
                       'model.AncestryChanged:Connect('):
            self.assertIn(signal, self.lifecycle)
        self.assertIn('agent.lifecycleConnections = {', self.lifecycle)
        self.assertIn('connection:Disconnect()', self.lifecycle)
        self.assertIn('agent.lifecycleConnections = nil', self.lifecycle)
        self.assertIn('xpcall(runAgent, debug.traceback, agent)', self.lifecycle)
        self.assertIn('if agent then releaseAgent(agent) end', self.lifecycle)

    def test_death_cancels_delayed_hit_and_navigation(self):
        death = self.lifecycle.split('local function stopOnDeath(', 1)[1].split('local function registerModel(', 1)[0]
        for expected in ('agent.attackSerial += 1', 'agent.attacking = false',
                         'CombatState.ClearTarget(agent)', 'AttackExecutor.ClearPursuit(agent)',
                         'Navigation.StopNavigation(agent)', 'Presentation.Stop(agent)',
                         'Facing.Stop(model)', '"MonsterCombatActive", false'):
            self.assertIn(expected, death)
        self.assertIn('agent.attackSerial ~= serial', self.attack)

    def test_release_is_idempotent_and_cleans_chase(self):
        body = self.lifecycle.split('local function releaseAgent(', 1)[1].split('local function stopOnDeath(', 1)[0]
        self.assertIn('if agents[model] ~= agent then return end', body)
        self.assertIn('agents[model] = nil', body)
        self.assertIn('agent.active = false', body)
        self.assertIn('Navigation.ClearPath(agent)', body)
        self.assertIn('CombatState.ClearTarget(agent)', body)
        self.assertIn('AttackExecutor.ClearPursuit(agent)', body)
        self.assertIn('Presentation.Stop(agent)', body)
        self.assertIn('agent.attackSerial += 1', body)
        self.assertIn('pathBlockedConnection:Disconnect()', self.nav)
        self.assertIn('if not agent.active then return end', self.nav)

    def test_folder_observers_have_defined_lifetime(self):
        self.assertIn('if watchedFolders[folder] then return end', self.lifecycle)
        self.assertIn('folder.ChildAdded:Connect(', self.lifecycle)
        self.assertIn('folder.Destroying:Connect(', self.lifecycle)
        self.assertIn('folder.AncestryChanged:Connect(', self.lifecycle)
        self.assertIn('if folder.Parent ~= Workspace then unwatchFolder(folder) end', self.lifecycle)
        self.assertIn('for _, connection in ipairs(connections) do connection:Disconnect() end', self.lifecycle)
        self.assertIn('if model:IsDescendantOf(folder) then table.insert(toRelease, agent) end', self.lifecycle)
        self.assertIn('for _, agent in ipairs(toRelease) do releaseAgent(agent) end', self.lifecycle)

    def test_old_combat_and_navigation_are_unchanged(self):
        for expected in ('AttackExecutor.ClearPursuit(agent)', 'Presentation.PlayRun(agent)',
                         'CombatState.Decide(', 'TARGET_SCAN_INTERVAL = 0.30',
                         'THINK_INTERVAL = 0.10'):
            self.assertIn(expected, self.ai)
        self.assertIn('AgentRadius = 1, AgentHeight = 4, AgentCanJump = false, WaypointSpacing = 3', self.nav)
        self.assertNotIn('ActorChaseNavigator', self.ai + self.lifecycle + self.nav)

    def test_single_heartbeat_and_no_global_per_agent_watcher(self):
        self.assertNotIn('RunService.Heartbeat:Connect', self.lifecycle)
        self.assertNotIn('PathfindingService', self.lifecycle)
        self.assertNotIn('DamageService', self.lifecycle)
        self.assertNotIn('Workspace:Raycast', self.lifecycle)
        self.assertIn('return table.freeze(MonsterAgentLifecycle)', self.lifecycle)

if __name__ == '__main__':
    unittest.main()
