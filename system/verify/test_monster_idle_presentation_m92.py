"""M92 monster idle presentation extraction: structural source contracts.

These tests do not execute Roblox AnimationTracks/Animator; Studio Play is required.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
MONSTER = ROOT / "src/server/monster"


def read(name):
    return (MONSTER / (name + ".luau")).read_text(encoding="utf-8")


class MonsterIdlePresentationM92Tests(unittest.TestCase):
    def test_presentation_isolated_from_population_and_startup(self):
        spawner, idle = read("MonsterSpawnerService"), read("MonsterIdlePresentation")
        self.assertIn('WaitForChild("MonsterIdlePresentation")', spawner)
        self.assertEqual(spawner.count("MonsterIdlePresentation.new(spawnRandom)"), 1)
        self.assertIn('return table.freeze(MonsterIdlePresentation)', idle)
        self.assertIn('return table.freeze({', idle)
        self.assertNotIn('WaitForChild("MonsterSpawnerService")', idle)
        for forbidden in ('ServerStorage', 'Workspace', 'state.instances', 'task.spawn(', 'task.delay(', 'RunService.PreAnimation', 'MonsterAIService'):
            self.assertNotIn(forbidden, idle)
        self.assertIn('MonsterWanderController.new(spawnRandom, spawnGeometry, idlePresentation)', spawner)
        self.assertIn('stopIdleState = idlePresentation.stopIdleState', spawner)
        self.assertIn('stopTrack = idlePresentation.stopTrack', spawner)
        self.assertNotIn('local function weightedIdleChoice(', spawner)
        self.assertNotIn('local function playBaseIdle(', spawner)

    def test_same_rng_draw_count_weights_and_safety_gates(self):
        spawner, idle = read("MonsterSpawnerService"), read("MonsterIdlePresentation")
        self.assertEqual(spawner.count('Random.new()'), 1)
        self.assertNotIn('Random.new()', idle)
        self.assertEqual(idle.count('spawnRandom:NextNumber(0, total)'), 1)
        for snippet in (
            'total += math.max(1, finite(choice.row and choice.row.weight, 100))',
            'cursor += math.max(1, finite(choice.row and choice.row.weight, 100))',
            'if roll <= cursor then',
            'return choices[#choices]',
            'entry.dying or entry.wandering or entry.activeIdleSpecial ~= nil',
            'model:GetAttribute("InCombat") == true or model:GetAttribute("MonsterCombatActive") == true',
            'if not choice or choice.role ~= "special" then',
            'entry.activeIdleSpecial = choice',
            'entry.activeIdleSpecial = nil',
            '("special_%02d"):format(math.max(1, math.floor(finite(choice.row.variant, 1))))',
        ):
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, idle)
        self.assertIn('if isCurrent() then\n                    maybePlayIdleSpecial(model, entry)', idle)

    def test_native_track_speeds_and_combat_priorities_preserved(self):
        idle, spawner = read("MonsterIdlePresentation"), read("MonsterSpawnerService")
        for snippet in (
            'AnimationSpeedScaling.ResolveForAnimation(model, channel, track.Animation and track.Animation.AnimationId)',
            'track:AdjustSpeed(speed)',
            'track:Play(fadeTime, 1, speed)',
            'track:Stop(0.08)',
            'playTrackAtConfiguredSpeed(model, entry.idleTrack, "idle", 0.12)',
            'playTrackAtConfiguredSpeed(model, entry.combatIdleTrack, "combat_idle", 0.1)',
            'playTrackAtConfiguredSpeed(model, choice.track, "idle", 0.08)',
            'model:SetAttribute("MonsterAnimationState", "idle")',
            'model:SetAttribute("MonsterAnimationState", "combat_idle")',
            'model:SetAttribute("MonsterIdleVariant", "base")',
            'model:SetAttribute("MonsterIdleVariant", "combat")',
        ):
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, idle)
        self.assertIn('if entry.dying or model:GetAttribute("MonsterCombatActive") == true then', idle)
        self.assertIn('if entry.dying or model:GetAttribute("MonsterCombatActive") == true or model:GetAttribute("InCombat") == true then', idle)
        self.assertIn('if state.instances[model] ~= entry or entry.dying then', spawner)
        self.assertIn('if state.instances[model] ~= entry or entry.dying or model:GetAttribute("MonsterCombatActive") == true then', spawner)

    def test_idle_event_connections_owned_by_instance_and_not_module(self):
        spawner, idle = read("MonsterSpawnerService"), read("MonsterIdlePresentation")
        ordered = (
            'entry.connections = {}',
            'state.instances[model] = entry',
            'idlePresentation.BindIdleEvents(model, entry, function(signal, callback)',
            'idlePresentation.playBaseIdle(model, entry)',
            'wanderController:Start(state, model, entry)',
        )
        self.assertEqual(list(map(spawner.index, ordered)), sorted(map(spawner.index, ordered)))
        self.assertIn('watch(entry, signal, callback)', spawner)
        self.assertIn('table.insert(entry.connections, connection)', spawner)
        self.assertIn('connection:Disconnect()', spawner)
        self.assertLess(spawner.index('state.instances[model] = nil'), spawner.index('for _, connection in ipairs(entry.connections or {}) do'))
        self.assertIn('registerSignal(choice.track.Ended, function()', idle)
        self.assertIn('registerSignal(idleTrack.DidLoop, function()', idle)
        self.assertIn('if not isCurrent() or entry.dying or entry.activeIdleSpecial ~= choice then', idle)
        self.assertEqual(idle.count(':Connect('), 0)
        self.assertEqual(idle.count('task.spawn('), 0)

    def test_outside_modules_keep_old_api_contracts(self):
        wander = read("MonsterWanderController")
        death = read("MonsterDeathLifecycle")
        spawner = read("MonsterSpawnerService")
        for method in ('stopTrack', 'stopIdleState', 'playBaseIdle', 'playCombatIdleState', 'playTrackAtConfiguredSpeed'):
            self.assertIn('local ' + method + ' = presentation.' + method, wander)
            self.assertIn('        ' + method + ' = ' + method + ',', read("MonsterIdlePresentation"))
        self.assertIn('stopIdleState = idlePresentation.stopIdleState', spawner)
        self.assertIn('stopTrack = idlePresentation.stopTrack', spawner)
        self.assertIn('stopIdleState(entry)', death)
        self.assertIn('stopTrack(entry.combatIdleTrack)', death)
        self.assertIn('deathLifecycle:Maintain(state, model, entry, deltaTimeSim)', spawner)
        self.assertIn('releaseInstance(state, model, true)', death)


if __name__ == '__main__':
    unittest.main()
