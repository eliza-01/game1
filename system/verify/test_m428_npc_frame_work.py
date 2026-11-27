"""M428 source contracts; actual rendering/physics still need Studio play."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


class NpcFrameWorkM428(unittest.TestCase):
    def test_retired_probe_has_no_automatic_runtime_cost(self):
        self.assertNotIn('NpcGroundComparisonService', read('src/server/bootstrap/ServiceCatalog.luau'))
        self.assertFalse((ROOT / 'src/server/dev/NpcGroundComparisonService.luau').exists())

    def test_mount_noop_keeps_alignment_and_uses_live_grip(self):
        src = read('src/shared/rig/BoneModelMount.luau')
        body = src.split('function BoneModelMount.Place(', 1)[1].split('function BoneModelMount.CreateGrip(', 1)[0]
        self.assertIn('local gripFrame = grip.WorldCFrame', body)
        self.assertIn('aligned(gripFrame, socketFrame)', body)
        self.assertIn('target:ToObjectSpace(actual)', src)
        for component in ('errorFrame.Position.Magnitude', 'errorFrame.LookVector:Dot', 'errorFrame.UpVector:Dot'):
            self.assertIn(component, src)
        self.assertLess(body.index('then return true end'), body.index('model:PivotTo('))
        self.assertIn('local delta = socketFrame * gripFrame:Inverse()', body)
        self.assertEqual(body.count('model:PivotTo('), 1)

    def test_inactive_sampler_stops_and_reuse_resumes_same_phase(self):
        sampler = read('src/client/actor/ActorLocomotionSampler.luau')
        suspend = sampler.split('function ActorLocomotionSampler:Suspend()', 1)[1].split('function ActorLocomotionSampler:Resume', 1)[0]
        resume = sampler.split('function ActorLocomotionSampler:Resume', 1)[1].split('function ActorLocomotionSampler:SetPlaybackSpeed', 1)[0]
        self.assertIn('self.track:Stop(0)', suspend)
        self.assertLess(resume.index('self.track:Play('), resume.index('self:SetPhase(phase)'))
        self.assertIn('(self.proxy:GetPivot().Position - position).Magnitude >= 8', sampler)
        for path in ('src/client/actor/NpcAttackLocomotionController.luau', 'src/client/monster/MonsterAttackLocomotionController.luau'):
            source = read(path)
            self.assertIn('Pool:Acquire(', source)
            self.assertIn('Pool:Release(', source)
            self.assertIn('Pool:Cleanup(', source)
        pool = read('src/client/actor/SamplerPool.luau')
        self.assertIn('pcall(sampler.Suspend, sampler)', pool)
        self.assertIn('pcall(matching.Resume, matching, speed, phase)', pool)

    def test_npc_budget_counts_existing_leases_and_failed_loads_back_off(self):
        source = read('src/client/actor/NpcAttackLocomotionController.luau')
        step = source.split('local function step(', 1)[1].split('function Controller.Start()', 1)[0]
        pool = read('src/client/actor/SamplerPool.luau')
        self.assertLess(pool.index('self.resident >= self.limit'), pool.index('pcall(factory)'))
        self.assertIn('acquire(entry)', step)
        self.assertIn('Pool:Release(sampler)', source)
        self.assertIn('os.clock() < (entry.retrySamplerAt or 0)', source)
        self.assertIn('entry.retrySamplerAt = os.clock() + 2', source)
        self.assertNotIn('elseif not wants then\n            active[entry] = nil', step)

    def test_attack_exit_hands_off_chase_before_presentation_ends(self):
        source = read('src/server/npc/NpcCombatAIService.luau')
        body = source.split('-- Hand off pursuit in this callback', 1)[1].split('local function tickAgent(', 1)[0]
        self.assertIn('HomeLeash.NoDamageTimeout', body)
        self.assertLess(body.index('chaseTarget(agent, targetRoot)'), body.index('agent.presentation.EndAttack()'))
        helper = source.split('local function chaseTarget(', 1)[1].split('local function beginAttack(', 1)[0]
        self.assertIn('agent.presentation.SetCombatMoving(true)', helper)
        self.assertIn('agent.navigator:Chase(targetRoot.Position, speed)', helper)
        self.assertIn('chaseTarget(agent, targetRoot)', source.split('local function tickAgent(', 1)[1])
        self.assertIn('beginAttack(agent, target, true)', source)

    def test_chase_progress_is_not_measured_from_spawn_or_idle(self):
        source = read('src/server/actor/ActorChaseNavigator.luau')
        body = source.split('function Navigator:Chase(', 1)[1].split('function Navigator:Stop()', 1)[0]
        reset = body.split('if self.mode == "" then', 1)[1].split('end', 1)[0]
        self.assertIn('self.progressAt = now', reset)
        self.assertIn('self.progressPosition = self.root.Position', reset)
        self.assertLess(body.index('self.progressAt = now'), body.index('local progressed ='))

    def test_running_track_only_receives_changed_speed(self):
        source = read('src/server/npc/NpcAnimationTracks.luau')
        self.assertIn('if clip.track.IsPlaying then', source)
        self.assertIn('if clip.playbackSpeed ~= speed then clip.track:AdjustSpeed(speed) end', source)
        self.assertIn('if entity:GetAttribute("AnimationPlaybackSpeedPercent") ~= percent then', source)


if __name__ == '__main__':
    unittest.main()
