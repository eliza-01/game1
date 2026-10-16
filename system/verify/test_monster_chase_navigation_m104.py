"""M104: source-level contracts protecting the original Monster chase algorithm.

This suite checks the module boundary and regression-sensitive branch order, not
actual Roblox motion. Test blocked paths and movement transitions in Studio.
"""
from pathlib import Path
import unittest

MONSTER = Path(__file__).resolve().parents[2] / "src/server/monster"


def read(filename):
    return (MONSTER / filename).read_text(encoding="utf-8-sig")


class MonsterChaseNavigationM104(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ai = read("MonsterAIService.luau")
        cls.nav = read("MonsterChaseNavigation.luau")
        cls.attack = read("MonsterAttackExecutor.luau")
        cls.wander = read("MonsterWanderController.luau")

    def test_navigator_is_only_owner_of_general_chase_path(self):
        self.assertIn('require(script.Parent:WaitForChild("MonsterChaseNavigation"))', self.ai)
        for method in ("ClearPath", "StopNavigation", "RunSpeedStuds", "NavigateTo"):
            self.assertIn(f"Navigation.{method}", self.ai)
        self.assertIn('Navigation.Initialize(agent)', self.ai)
        for token in ('PathfindingService', 'CreatePath(', 'ComputeAsync(', 'pathBlockedConnection =',
                      'local function rebuildPath(', 'local function navigateTo('):
            self.assertNotIn(token, self.ai)
        self.assertNotIn('DamageService', self.nav)
        self.assertNotIn('HostilePursuitRegistry', self.nav)
        self.assertNotIn('AttackTimelineConfig', self.nav)

    def test_original_path_config_and_refresh_intervals(self):
        for constant in ('DIRECT_REFRESH_SECONDS = 0.30', 'PATH_REFRESH_SECONDS = 0.75',
                         'PATH_TARGET_MOVE_THRESHOLD = 3', 'STUCK_CHECK_SECONDS = 0.80',
                         'STUCK_PROGRESS_STUDS = 0.35', 'WAYPOINT_TOLERANCE = 1.25',
                         'AgentRadius = 1, AgentHeight = 4, AgentCanJump = false, WaypointSpacing = 3'):
            self.assertIn(constant, self.nav)
        self.assertIn('pcall(function() path:ComputeAsync(agent.root.Position, destination) end)', self.nav)
        self.assertIn('if ok and path.Status == Enum.PathStatus.Success then', self.nav)
        self.assertIn('agent.pathIndex = math.min(2, #agent.pathWaypoints)', self.nav)

    def test_blocked_connection_and_cleanup_stay_together(self):
        self.assertIn('agent.pathBlockedConnection:Disconnect(); agent.pathBlockedConnection = nil', self.nav)
        self.assertIn('path.Blocked:Connect(function(blockedIndex)', self.nav)
        self.assertIn('if agent.active and blockedIndex >= agent.pathIndex then agent.pathFallbackRequested = true end', self.nav)
        for field in ('agent.path = nil', 'agent.pathWaypoints = nil', 'agent.pathIndex = 1',
                      'agent.pathFallbackRequested = false'):
            self.assertIn(field, self.nav)
        self.assertLess(self.nav.index('clearPath(agent)\n    agent.navigationMode = "Path"'),
                        self.nav.index('path.Blocked:Connect('))

    def test_stuck_detection_and_direct_fallback_branch_order(self):
        chase = self.nav.split('local function navigateTo(', 1)[1].split('function MonsterChaseNavigation.Initialize(', 1)[0]
        self.assertLess(chase.index('local progressed = '), chase.index('local targetMoved = '))
        self.assertLess(chase.index('if agent.pathFallbackRequested then'),
                        chase.index('elseif not agent.navigating or agent.navigationMode ~= "Direct"'))
        self.assertIn('rebuildPath(agent, destination, speed)', chase)
        self.assertIn('issueDirectMove(agent, destination, speed)', chase)
        self.assertIn('agent.pathIndex += 1', chase)
        self.assertIn('horizontalDistance(agent.root.Position, waypoint.Position) <= WAYPOINT_TOLERANCE', chase)

    def test_speed_conversion_and_stop_semantics(self):
        self.assertIn('CharacterMovementConfig.DefaultRunSpeed', self.nav)
        self.assertIn('CharacterMovementConfig.RobloxSpeed(nil, runSpeed, "Run")', self.nav)
        self.assertIn('agent.humanoid:Move(Vector3.zero, false)', self.nav)
        self.assertIn('agent.humanoid:MoveTo(agent.root.Position)', self.nav)
        self.assertIn('agent.humanoid:MoveTo(destination)', self.nav)
        self.assertIn('agent.humanoid.AutoRotate = true', self.nav)

    def test_state_initialized_before_agent_registration(self):
        self.assertLess(self.ai.index('Navigation.Initialize(agent)'), self.ai.index('agents[model] = agent'))
        self.assertIn('agent.lastProgressPosition = agent.root.Position', self.nav)
        self.assertIn('agent.lastProgressAt = os.clock()', self.nav)
        for name in ('navigating', 'navigationMode', 'nextPathAt', 'pathWaypoints',
                     'pathBlockedConnection', 'lastProgressAt'):
            self.assertIn('agent.' + name, self.nav)
            self.assertNotIn('            ' + name + ' = ', self.ai)

    def test_ai_uses_exclusive_movement_ownership_during_attack(self):
        active = self.ai.split('if action == "AttackActive" then', 1)[1].split('elseif action == "BeginAttack"', 1)[0]
        self.assertNotIn('navigateTo(', active)
        chase = self.ai.split('elseif action == "Chase" then', 1)[1].split('elseif agent.model:GetAttribute', 1)[0]
        self.assertIn('AttackExecutor.ClearPursuit(agent)', chase)
        self.assertIn('navigateTo(agent, targetRoot.Position, runSpeedStuds(agent))', chase)
        self.assertIn('AttackExecutor.Begin(agent, target, AttackMovement, random)', self.ai)
        self.assertIn('StopNavigation = stopNavigation', self.ai)
        self.assertIn('RunSpeedStuds = runSpeedStuds', self.ai)
        self.assertIn('agent.attackPursuit:Step(', self.attack)
        self.assertNotIn('PathfindingService', self.attack)

    def test_lifecycle_cleans_up_path_and_targets(self):
        leave = self.ai.split('local function leaveCombat(', 1)[1].split('local function updateTarget(', 1)[0]
        death = self.ai.split('GetAttributeChangedSignal("LifeState")', 1)[1].split('model.Destroying:Connect(', 1)[0]
        destroy = self.ai.split('model.Destroying:Connect(', 1)[1].split('task.spawn(runAgent', 1)[0]
        for body in (leave, death):
            self.assertIn('stopNavigation(agent)', body)
            self.assertIn('AttackExecutor.ClearPursuit(agent)', body)
        self.assertIn('clearPath(agent)', destroy)
        self.assertIn('CombatState.ClearPursuit(agent)', destroy)
        self.assertIn('agent.active = false', destroy)

    def test_wander_and_attack_pursuit_are_not_replaced(self):
        self.assertIn('function MonsterChaseNavigation.Initialize', self.nav)
        self.assertIn('return table.freeze(MonsterChaseNavigation)', self.nav)
        self.assertIn('ActorAttackPursuit', self.attack)
        self.assertIn('MonsterWanderController', self.wander)
        self.assertNotIn('ActorChaseNavigator', self.ai + self.nav + self.attack)


if __name__ == '__main__':
    unittest.main()
