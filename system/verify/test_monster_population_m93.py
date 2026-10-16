"""M93: monster spawn-slot and respawn ownership contracts.

Static Luau contracts: Roblox instance lifecycle needs Studio Play verification.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
MONSTER = ROOT / "src/server/monster"


def read(module):
    return (MONSTER / f"{module}.luau").read_text(encoding="utf-8")


class MonsterPopulationM93Tests(unittest.TestCase):
    def test_population_is_injected_and_independent_of_spawner(self):
        spawner = read("MonsterSpawnerService")
        population = read("MonsterPopulationController")
        self.assertIn('WaitForChild("MonsterPopulationController")', spawner)
        self.assertEqual(spawner.count('MonsterPopulationController.new(spawnOne)'), 1)
        self.assertIn('function MonsterPopulationController.new(spawnOne: (any) -> Model?): any', population)
        self.assertIn('return table.freeze(MonsterPopulationController)', population)
        self.assertNotIn('WaitForChild("MonsterSpawnerService")', population)
        self.assertNotIn('WaitForChild("MonsterAIService")', population)
        for forbidden in ('AnimationTrack', 'Humanoid', 'EntityHitboxService', 'Random.new()', 'RunService', 'Workspace', 'Instance.new(', ':Destroy()', ':Connect(', 'task.spawn('):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, population)
        self.assertNotIn('local function stateFill(', spawner)
        self.assertNotIn('local function recordAppliesHere(', spawner)
        self.assertNotIn('task.delay(', spawner)

    def test_record_filter_and_start_sequence_unchanged(self):
        spawner, population = read("MonsterSpawnerService"), read("MonsterPopulationController")
        for expected in (
            'local SpawnRegistry = require(script.Parent:WaitForChild("MonsterSpawnRegistry"))',
            'if record.enabled == false then',
            'local placeId = math.floor(finite(record.placeId, 0))',
            'return placeId == 0 or game.PlaceId == 0 or placeId == game.PlaceId',
            'for _, record in ipairs(SpawnRegistry.records or {}) do',
            'if recordAppliesHere(record) then',
            'states[tostring(record.spawnId or count + 1)] = state',
            'fill(state)\n                count += 1',
            'state.fill = function()\n                    fill(state)\n                end',
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, population)
        self.assertLess(spawner.index('RunService.PreAnimation:Connect('), spawner.index('local count = population:Start()'))
        self.assertIn('for _, state in pairs(population:States()) do', spawner)
        self.assertIn('print(("[game1][monster-spawn] %d authored spawn(s) active"):format(count))', spawner)

    def test_max_alive_slot_count_keeps_dying_and_deathidle(self):
        population = read("MonsterPopulationController")
        self.assertIn('local target = math.max(1, math.floor(finite(state.record.maxAlive, 1)))', population)
        self.assertIn('for model in pairs(state.instances) do', population)
        self.assertIn('if model.Parent then\n                alive += 1', population)
        self.assertIn('while liveCount(state) + state.creating < target do', population)
        self.assertIn('if not spawnReserved(state) then\n                break\n            end', population)
        self.assertIn('if not state.enabled then\n            return', population)
        self.assertIn('pcall(spawnOne, state)', population)  # one guarded creator shared by fill and timer
        self.assertNotIn('LifeState', population)
        self.assertNotIn('Health', population)

    def test_release_order_and_external_destroy_semantics(self):
        spawner = read("MonsterSpawnerService")
        population = read("MonsterPopulationController")
        ordered = (
            'local entry = state.instances[model]',
            'if entry == nil then',
            'population:UnregisterInstance(state, model)',
            'DeathLifecycleService.Cancel(model)',
            'wanderController:Dispose(entry)',
            'for _, connection in ipairs(entry.connections or {}) do',
            'idlePresentation.stopIdleState(entry)',
            'if externallyDestroying then',
            'if model.Parent and not externallyDestroying then',
            'if scheduleRespawn then\n        population:ScheduleRespawn(state, entry.diedAt)',
        )
        self.assertEqual(list(map(spawner.index, ordered)), sorted(map(spawner.index, ordered)))
        self.assertIn('state.instances[model] = entry', population)
        self.assertIn('state.instances[model] = nil', population)
        self.assertIn('releaseInstance(state, model, false, true)', spawner)
        self.assertIn('releaseInstance(state, model, true)', read("MonsterDeathLifecycle"))

    def test_respawn_deadline_belongs_to_death_and_slot_frees_after_corpse_release(self):
        population, spawner, death = (read(name) for name in (
            "MonsterPopulationController", "MonsterSpawnerService", "MonsterDeathLifecycle"
        ))
        self.assertIn('DeathLifecycleService.BeginDeathIdle(model, entry.navigationRoot, entry.visual, function()', death)
        self.assertIn('releaseInstance(state, model, true)', death)
        self.assertIn('local delaySeconds = math.max(0, finite(state.record.respawnSeconds, 10))', population)
        self.assertIn('entry.diedAt = os.clock()', spawner)
        self.assertIn('local remaining = math.max(0, delaySeconds - elapsed)', population)
        self.assertIn('task.delay(remaining, function()', population)
        self.assertIn('if liveCount(state) + state.creating < target then\n                    spawnReserved(state)', population)
        self.assertNotIn('state.fill()\n', population)
        self.assertEqual(population.count('task.delay('), 1)
        self.assertEqual(spawner.count('population:ScheduleRespawn(state, entry.diedAt)'), 1)
        self.assertNotIn('task.delay(', death)
        self.assertNotIn('task.delay(', read("MonsterWanderController"))

    def test_random_order_and_instance_setup_untouched(self):
        spawner = read("MonsterSpawnerService")
        population = read("MonsterPopulationController")
        self.assertEqual(spawner.count('Random.new()'), 1)
        self.assertNotIn('Random.new()', population)
        self.assertIn('spawnRandom:NextInteger(1000, 9999)', spawner)
        self.assertIn('spawnGeometry:RandomSpawnPoint(record)', spawner)
        self.assertIn('spawnRandom:NextNumber(0, math.pi * 2)', spawner)
        ordered = (
            'MonsterRigBuilder.PrepareVisual(model)',
            'MonsterRigBuilder.EnsureRuntimeAnimationRoot(visual)',
            'spawnGeometry:RandomSpawnPoint(record)',
            'MonsterRigBuilder.GroundAlign(model, surface, yaw)',
            'MonsterInitialAttributes.Apply(model, definition, record, instanceId)',
            'MonsterRigBuilder.CreateNavigationRig(model, visual, visualRoot, surface, yaw)',
            'EntityHitboxService.Attach(model, visual)',
            'MonsterAnimationTrackFactory.Load(',
            'population:RegisterInstance(state, model, entry)',
            'idlePresentation.BindIdleEvents(',
            'wanderController:Start(state, model, entry)',
        )
        self.assertEqual(list(map(spawner.index, ordered)), sorted(map(spawner.index, ordered)))


if __name__ == '__main__':
    unittest.main()
