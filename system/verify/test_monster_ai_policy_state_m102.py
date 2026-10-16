"""M102 boundaries: target selection, combat state authority and unchanged movement.

Source-level checks document the wiring; Studio Play still has to verify behavior.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
MONSTER = ROOT / 'src/server/monster'


def read(filename):
    return (MONSTER / filename).read_text(encoding='utf-8-sig')


class MonsterAiM102Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ai = read('MonsterAIService.luau')
        cls.targets = read('MonsterTargetPolicy.luau')
        cls.state = read('MonsterCombatState.luau')
        cls.attack = read('MonsterAttackExecutor.luau')
        cls.presentation = read('MonsterCombatPresentation.luau')

    def test_service_uses_two_narrow_modules(self):
        self.assertIn('require(script.Parent:WaitForChild("MonsterTargetPolicy"))', self.ai)
        self.assertIn('require(script.Parent:WaitForChild("MonsterCombatState"))', self.ai)
        self.assertIn('local rootOf = TargetPolicy.RootOf', self.ai)
        self.assertIn('local setState = CombatState.SetState', self.ai)
        self.assertNotIn('local function acquireNearestTarget(', self.ai)
        self.assertNotIn('local function attackStillConnects(', self.ai)
        self.assertNotIn('HostilePursuitRegistry.', self.ai)

    def test_target_filter_and_tie_breaker_are_preserved(self):
        for token in ('target.Parent ~= nil', 'target:GetAttribute("Damageable") == true',
                      'target:GetAttribute("LifeState")', 'rootOf(target) ~= nil',
                      'Players:GetPlayers()', 'closestDistance = aggroRadius(agent)',
                      'distance <= closestDistance', 'closest = character'):
            self.assertIn(token, self.targets)
        self.assertIn('local target = TargetPolicy.AcquireNearestTarget(agent)', self.ai)
        self.assertIn('now < agent.nextTargetScanAt', self.ai)
        self.assertIn('TARGET_SCAN_INTERVAL = 0.30', self.ai)

    def test_target_hit_geometry_and_los_still_run_at_hit_event(self):
        for token in ('local ATTACK_ARC_DEGREES = 110', 'local VERTICAL_TOLERANCE = 5',
                      'agent.root.CFrame.LookVector:Dot(delta.Unit)',
                      'Enum.RaycastFilterType.Exclude', 'FilterDescendantsInstances = {agent.model}',
                      'Workspace:Raycast(origin, destination - origin, params)',
                      'return hasLineOfSight(agent, target)'):
            self.assertIn(token, self.targets)
        hit = self.attack.split('task.delay(hitTime, function()', 1)[1].split('task.delay(duration, function()', 1)[0]
        self.assertLess(hit.index('TargetPolicy.AttackStillConnects(agent, target)'),
                        hit.index('DamageService.Apply('))
        self.assertIn('agent.attackSerial ~= serial', hit)

    def test_state_module_is_sole_owner_of_target_registration(self):
        self.assertIn('agent.target = target', self.state)
        self.assertIn('HostilePursuitRegistry.SetTarget(agent.model, target)', self.state)
        self.assertLess(self.state.index('HostilePursuitRegistry.SetTarget(agent.model, target)'),
                        self.state.index('setState(agent, "Aggro")'))
        self.assertIn('agent.target = nil', self.state)
        self.assertIn('HostilePursuitRegistry.Clear(agent.model)', self.state)
        self.assertIn('setState(agent, "Idle")', self.state)
        for token in ('MonsterTargetName', 'MonsterTargetUserId', 'MonsterCombatActive', 'MonsterAttackPhase'):
            self.assertIn(token, self.state)
        self.assertIn('CombatState.ClearTarget(agent)', self.ai)
        self.assertIn('CombatState.FinishExit(agent)', self.ai)

    def test_pure_decision_does_not_issue_movement_or_damage(self):
        decide = self.state.split('function MonsterCombatState.Decide(', 1)[1].split('\nend', 1)[0]
        self.assertIn('if not hasTarget then return "NoTarget" end', decide)
        self.assertIn('if attacking then return "AttackActive" end', decide)
        self.assertIn('if distance <= attackRadius then return "BeginAttack" end', decide)
        self.assertIn('return "Chase"', decide)
        for token in ('MoveTo(', 'DamageService', 'Workspace', 'task.', 'SetAttribute('):
            self.assertNotIn(token, decide)
        self.assertIn('CombatState.Decide(agent.attacking, targetRoot ~= nil, distance, attackRadius(agent))', self.ai)

    def test_chase_and_active_attack_remain_separate_movement_owners(self):
        self.assertIn('if action == "AttackActive" then', self.ai)
        self.assertIn('setState(agent, "Attack")', self.ai)
        self.assertIn('elseif action == "BeginAttack" then', self.ai)
        self.assertIn('AttackExecutor.Begin(agent, target, AttackMovement, random)', self.ai)
        self.assertIn('elseif action == "Chase" then', self.ai)
        self.assertIn('navigateTo(agent, targetRoot.Position, runSpeedStuds(agent))', self.ai)
        self.assertIn('maintainAttackPursuit(agent, target, serial, movement)', self.attack)
        self.assertIn('agent.attackPursuit:Step(targetRoot, attackRadius(agent), maximumSpeed)', self.attack)
        self.assertIn('PathfindingService:CreatePath({AgentRadius = 1, AgentHeight = 4, AgentCanJump = false, WaypointSpacing = 3})', self.ai)
        self.assertIn('issueDirectMove(agent, destination, speed)', self.ai)
        self.assertNotIn('ActorChaseNavigator', self.ai)

    def test_death_destruction_and_loop_end_clear_pursuit(self):
        run_end = self.ai.split('local function runAgent(', 1)[1].split('local function bindMonster(', 1)[0]
        self.assertIn('CombatState.ClearPursuit(agent)', run_end)
        death = self.ai.split('GetAttributeChangedSignal("LifeState")', 1)[1].split('model.Destroying:Connect(', 1)[0]
        destroy = self.ai.split('model.Destroying:Connect(', 1)[1].split('task.spawn(runAgent', 1)[0]
        self.assertIn('CombatState.ClearTarget(agent)', death)
        self.assertIn('agent.attackSerial += 1', death)
        self.assertIn('CombatState.ClearPursuit(agent)', destroy)
        self.assertIn('Facing.Stop(agent.model)', death)
        self.assertIn('Facing.Stop(agent.model)', destroy)

    def test_modules_keep_server_ownership_boundaries(self):
        for text in (self.state, self.targets, self.attack, self.presentation):
            self.assertIn('return table.freeze(', text)
            self.assertNotIn('RemoteEvent', text)
            self.assertNotIn('DataStoreService', text)
            self.assertNotIn('PathfindingService', text)
            if text is not self.attack:
                self.assertNotIn('DamageService', text)
        self.assertNotIn('HostilePursuitRegistry', self.targets)
        self.assertNotIn('Workspace:Raycast', self.state)


if __name__ == '__main__':
    unittest.main()
