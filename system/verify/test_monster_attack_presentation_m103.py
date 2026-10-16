"""M103 source-level contracts for attack timeline/presentation ownership.

These cannot simulate Roblox Humanoid or animation playback; validate in Studio.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2] / 'src/server/monster'

def read(name):
    return (ROOT / name).read_text(encoding='utf-8-sig')

class MonsterM103Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ai = read('MonsterAIService.luau')
        cls.presentation = read('MonsterCombatPresentation.luau')
        cls.attack = read('MonsterAttackExecutor.luau')
        cls.target = read('MonsterTargetPolicy.luau')
        cls.state = read('MonsterCombatState.luau')

    def test_coordinator_delegates_without_owning_damage_or_presentation(self):
        self.assertIn('require(script.Parent:WaitForChild("MonsterCombatPresentation"))', self.ai)
        self.assertIn('require(script.Parent:WaitForChild("MonsterAttackExecutor"))', self.ai)
        self.assertIn('AttackExecutor.Begin(agent, target, AttackMovement, random)', self.ai)
        self.assertIn('Presentation.PlayCombatIdle(agent)', self.ai)
        self.assertIn('Presentation.PlayRun(agent)', self.ai)
        self.assertNotIn('DamageService.Apply(', self.ai)
        self.assertNotIn('task.delay(hitTime', self.ai)
        self.assertNotIn('animator:LoadAnimation(', self.ai)

    def test_legacy_movement_remains_coordinator_owned(self):
        for token in ('PathfindingService:CreatePath({AgentRadius = 1, AgentHeight = 4, AgentCanJump = false, WaypointSpacing = 3})',
                      'path:ComputeAsync(agent.root.Position, destination)',
                      'agent.humanoid:MoveTo(destination)',
                      'local function navigateTo(',
                      'navigateTo(agent, targetRoot.Position, runSpeedStuds(agent))'):
            self.assertIn(token, self.ai)
        self.assertIn('RunSpeedStuds = runSpeedStuds', self.ai)
        self.assertIn('StopNavigation = stopNavigation', self.ai)
        self.assertNotIn('PathfindingService', self.attack)
        self.assertNotIn('PathfindingService', self.presentation)
        self.assertNotIn('ActorChaseNavigator', self.ai + self.attack + self.presentation)

    def test_attack_preserves_timing_and_serial_guard(self):
        self.assertIn('local timing = AttackTimelineConfig.ResolveRuntime(row.clipId, percent)', self.attack)
        self.assertIn('local duration = math.max(0.05, finite(timing.duration, 0.05))', self.attack)
        self.assertIn('agent.attackSerial += 1', self.attack)
        self.assertIn('agent.nextAttackAt = agent.attackEndsAt', self.attack)
        hit = self.attack.split('task.delay(hitTime, function()', 1)[1].split('task.delay(duration, function()', 1)[0]
        self.assertIn('agent.attackSerial ~= serial', hit)
        self.assertIn('agent.target ~= target', hit)
        self.assertIn('agent.model:GetAttribute("LifeState")', hit)
        self.assertLess(hit.index('TargetPolicy.AttackStillConnects(agent, target)'), hit.index('DamageService.Apply('))
        finish = self.attack.split('task.delay(duration, function()', 1)[1]
        self.assertIn('if not agent.active or agent.attackSerial ~= serial then return end', finish)
        self.assertIn('Facing.Stop(agent.model)', finish)
        self.assertIn('Presentation.StopAttack(agent)', finish)

    def test_attack_pursuit_is_distinct_from_general_chase(self):
        pursuing = self.attack.split('local function pursueDirectlyDuringAttack(', 1)[1].split('local function maintainAttackPursuit(', 1)[0]
        for token in ('agent.attackPursuit:Step(', 'clearAttackPursuit(agent)', 'MonsterAttackPursuitActive',
                      'Presentation.PublishAttackPursuitPlaybackSpeed'):
            self.assertIn(token, pursuing)
        self.assertNotIn('MoveTo(', pursuing)
        self.assertIn('RunService.Heartbeat:Wait()', self.attack)
        self.assertIn('agent.target == target', self.attack)
        self.assertIn('agent.attackSerial == serial', self.attack)

    def test_track_loading_and_animation_attributes_stay_in_presentation(self):
        for token in ('animator:LoadAnimation(animation)', 'animation:Destroy()', 'track.Priority = animationPriority(row.priority)',
                      'track.Looped = looped', 'MonsterAnimationState", "attack"',
                      'AnimationPlaybackSpeedPercent', 'MonsterAttackClipId',
                      'MonsterAnimationState", "combat_idle"', 'MonsterAnimationState", "run"'):
            self.assertIn(token, self.presentation)
        self.assertIn('if agent.attacking then', self.presentation)
        self.assertIn('if track.IsPlaying then track:AdjustSpeed(speed) else track:Play(0.08, 1, speed) end', self.presentation)
        self.assertIn('track:Stop(fade or 0.08)', self.presentation)
        self.assertNotIn('AnimationTrack', self.attack)
        self.assertNotIn('DamageService', self.presentation)

    def test_weighted_choice_uses_shared_random_and_original_scaling(self):
        self.assertIn('Presentation.WeightedRow(agent.attackRows, random)', self.attack)
        self.assertIn('local roll = random:NextNumber(0, total)', self.presentation)
        self.assertIn('math.max(1, finite(row.weight, 100))', self.presentation)
        self.assertIn('AnimationSpeedScaling.ResolveForAnimation(agent.model, "attack", row.animationId)', self.attack)
        self.assertIn('AnimationSpeedScaling.ResolveScaleForAnimation(agent.model, "run",', self.presentation)
        self.assertIn('math.abs(current - desired) > ATTACK_PURSUIT_PLAYBACK_EPSILON', self.presentation)

    def test_exit_and_death_cancel_late_hits_and_clear_state(self):
        leave = self.ai.split('local function leaveCombat(', 1)[1].split('local function updateTarget(', 1)[0]
        death = self.ai.split('GetAttributeChangedSignal("LifeState")', 1)[1].split('model.Destroying:Connect(', 1)[0]
        for text in (leave, death):
            self.assertIn('agent.attackSerial += 1', text)
            self.assertIn('AttackExecutor.ClearPursuit(agent)', text)
            self.assertIn('CombatState.ClearTarget(agent)', text)
            self.assertIn('Presentation.Stop(agent)', text)
        self.assertIn('CombatState.FinishExit(agent)', leave)
        self.assertIn('CombatState.ClearPursuit(agent)', self.ai)
        self.assertIn('HostilePursuitRegistry.SetTarget(agent.model, target)', self.state)

    def test_all_new_modules_are_narrow(self):
        for source in (self.attack, self.presentation):
            self.assertIn('return table.freeze(', source)
            self.assertNotIn('RemoteEvent', source)
            self.assertNotIn('DataStoreService', source)
        self.assertNotIn('HostilePursuitRegistry', self.attack + self.presentation)
        self.assertNotIn('DamageService.Apply(', self.target)

if __name__ == '__main__':
    unittest.main()
