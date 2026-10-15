"""M91: explicit ownership and transition contracts of extracted monster services.

Structural regression checks only: Roblox animation/physics must be Play-tested.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
MONSTER = ROOT / "src/server/monster"


def source(name):
    return (MONSTER / (name + ".luau")).read_text(encoding="utf-8")


class MonsterLifecycleM91Tests(unittest.TestCase):
    def test_controllers_are_independent_of_population_and_created_once(self):
        spawner = source("MonsterSpawnerService")
        wander = source("MonsterWanderController")
        death = source("MonsterDeathLifecycle")
        for name in ("MonsterWanderController", "MonsterDeathLifecycle"):
            self.assertIn(f'WaitForChild("{name}")', spawner)
            self.assertIn(f'return table.freeze({name})', source(name))
            self.assertNotIn('WaitForChild("MonsterSpawnerService")', source(name))
        self.assertEqual(spawner.count("MonsterWanderController.new("), 1)
        self.assertEqual(spawner.count("MonsterDeathLifecycle.new("), 1)
        self.assertIn("spawnRandom, spawnGeometry", spawner)
        self.assertNotIn("task.spawn(", spawner)
        self.assertNotIn("DeathAnimationPolicy", spawner)
        self.assertIn("local function stateFill(state: any)", spawner)
        self.assertIn("local function releaseInstance", spawner)
        self.assertNotIn("task.delay(", wander)
        self.assertNotIn("task.delay(", death)

    def test_wander_reuses_rng_and_move_lifecycle(self):
        wander = source("MonsterWanderController")
        snippets = (
            "spawnRandom:NextNumber(0.35, 1.35)",
            "spawnRandom:NextNumber(WANDER_PAUSE_MIN_SECONDS, WANDER_PAUSE_MAX_SECONDS)",
            "spawnGeometry:ChooseWanderTarget(state.record, navigationRoot.Position)",
            "humanoid.MoveToFinished:Connect",
            "humanoid:MoveTo(destination)",
            "MonsterSpawnGeometry.HorizontalDistance(navigationRoot.Position, destination)",
            "CharacterMovementConfig.RobloxSpeed",
            'model:GetAttribute("MonsterCombatActive") == true',
            'model:GetAttribute("InCombat") == true',
            "entry.wanderMoveConnection:Disconnect()",
            "entry.wanderGeneration ~= moveGeneration",
            "pcall(task.cancel, thread)",
        )
        for snippet in snippets:
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, wander)
        self.assertEqual(wander.count("task.spawn("), 1)
        self.assertIn("and entry.wanderGeneration == moveGeneration", wander)
        self.assertLess(wander.index("entry.wanderMoveConnection:Disconnect()"), wander.index("local function startWanderLoop"))
        self.assertIn("function controller:Stop(entry: any)", wander)
        self.assertIn("function controller:Dispose(entry: any)", wander)

    def test_death_terminal_hold_then_sink_then_respawn_handoff(self):
        death = source("MonsterDeathLifecycle")
        spawner = source("MonsterSpawnerService")
        ordered = [
            'model:SetAttribute("DeathAnimationStartedAt", os.clock())',
            'model:SetAttribute("DeathTerminalPoseHeld", false)',
            'stopWanderMovement(entry)',
            'DeathAnimationPolicy.Start(track,',
        ]
        self.assertEqual(list(map(death.index, ordered)), sorted(map(death.index, ordered)))
        for required in (
            'DeathAnimationPolicy.LatchVisibleTerminalPose(track, deltaTimeSim)',
            'model:SetAttribute("DeathAnimationTerminalTime", terminalTime)',
            'model:SetAttribute("DeathTerminalPoseHeld", true)',
            'DeathLifecycleService.BeginDeathIdle(model, entry.navigationRoot, entry.visual, function()',
            'releaseInstance(state, model, true)',
            'assert(started, "DeathIdle lifecycle must start exactly once',
            'or tostring(model:GetAttribute("LifeState") or "") ~= "Dying"',
        ):
            self.assertIn(required, death)
        self.assertIn('RunService.PreAnimation:Connect(function(deltaTimeSim)', spawner)
        self.assertIn('deathLifecycle:Maintain(state, model, entry, deltaTimeSim)', spawner)
        self.assertIn('deathLifecycle:Begin(state, model, entry)', spawner)
        self.assertIn('if scheduleRespawn and state.enabled then', spawner)
        self.assertIn('state.fill()', spawner)
        self.assertIn('if model.Parent then\n            alive += 1', spawner)

    def test_all_per_instance_event_connections_are_owned_and_released(self):
        spawner = source("MonsterSpawnerService")
        self.assertEqual(spawner.count('watch(entry, '), 8)
        self.assertIn('watch(entry, signal, callback)', spawner)
        self.assertIn('idlePresentation.BindIdleEvents(model, entry, function(signal, callback)', spawner)
        self.assertIn('entry.connections = {}', spawner)
        self.assertIn('table.insert(entry.connections, connection)', spawner)
        self.assertIn('for _, connection in ipairs(entry.connections or {}) do', spawner)
        self.assertIn('connection:Disconnect()', spawner)
        self.assertIn('wanderController:Dispose(entry)', spawner)
        self.assertLess(spawner.index('state.instances[model] = nil'), spawner.index('wanderController:Dispose(entry)'))
        self.assertLess(spawner.index('wanderController:Dispose(entry)'), spawner.index('model:Destroy()', spawner.index('local function releaseInstance')))
        self.assertIn('watch(entry, model.Destroying, function()', spawner)
        self.assertIn('releaseInstance(state, model, false, true)', spawner)
        self.assertIn('DeathLifecycleService.Cancel(model)', spawner)
        self.assertNotIn('model.Destroying:Connect(function()', spawner)


if __name__ == '__main__':
    unittest.main()
