"""M94 NPC combat recovery + locomotion contracts, source-level checks only.

These tests do NOT simulate Roblox Humanoid physics, Animator or replicated attrs.
Manual Play is required. Tests are intentionally narrow and cover transition
ordering, policy ownership, resource cleanup and other actor isolation.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
NPC = ROOT / 'src/server/npc'


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


class NpcMovementM94Tests(unittest.TestCase):
    def test_policy_and_timing_share_no_actor_implementation(self):
        policy = read('src/shared/npc/NpcMovementPolicy.luau')
        self.assertIn('NpcMovementPolicy.RecoverySeconds = 2', policy)
        self.assertIn('if phase == "Combat" then "Run" else "Walk"', policy)
        self.assertIn('CharacterMovementConfig.RobloxSpeed(nil, runSpeed, NpcMovementPolicy.ModeFor(phase))', policy)
        self.assertNotIn('Humanoid:', policy)
        self.assertNotIn('AnimationTrack', policy)
        self.assertNotIn('NpcCombatAIService', policy)

    def test_recovery_is_per_agent_without_parallel_timers(self):
        recovery = (NPC / 'NpcCombatRecovery.luau').read_text()
        ai = (NPC / 'NpcCombatAIService.luau').read_text()
        for needle in ('function NpcCombatRecovery.new()', 'self.deadline = now + Policy.RecoverySeconds',
                       'function NpcCombatRecovery:Ready(now: number)',
                       'now >= self.deadline', 'function NpcCombatRecovery:Cancel()'):
            self.assertIn(needle, recovery)
        self.assertNotIn('task.delay(', recovery)
        self.assertNotIn('RunService', recovery)
        self.assertIn('recovery = NpcCombatRecovery.new()', ai)
        self.assertIn('if agent.recovery:Pending() then', ai)
        self.assertIn('if agent.recovery:Ready(now) then', ai)
        self.assertIn('agent.recovery:Cancel()', ai)
        self.assertIn('TICK_SECONDS = 0.1', ai)

    def test_kill_waits_before_peace_and_clears_target_without_damage(self):
        ai = (NPC / 'NpcCombatAIService.luau').read_text()
        recover = ai.split('local function beginRecovery(', 1)[1].split('local function startReturn(', 1)[0]
        self.assertLess(recover.index('stopAttack(agent)'), recover.index('agent.target = nil'))
        self.assertIn('agent.presentation.SetCombatActive(true)', recover)
        self.assertIn('CombatStateService.Activate(agent.model)', recover)
        self.assertIn('agent.presentation.SetCombatMoving(false)', recover)
        self.assertIn('setState(agent, "Recover")', recover)
        self.assertIn('pinAtRest(agent, true)', recover)
        self.assertNotIn('CombatStateService.Clear', recover)
        self.assertNotIn('agent.navigator:Chase', recover)
        self.assertIn('agent.recovery:Begin(agent.targetKilledAt or os.clock())', recover)
        after = ai.split('local function tickAgent(', 1)[1]
        self.assertLess(after.index('if agent.recovery:Pending() then'), after.index('if not agent.retaliate then'))
        self.assertIn('startReturn(agent, false)', after)
        self.assertIn('startReturn(agent, true)', ai)
        self.assertIn('agent.targetKilledAt = os.clock()', ai)
        self.assertIn('return -- do not enter Return while the combat recovery gate is pending', after)

    def test_reengagement_cancels_recovery_and_death_disposes_it(self):
        ai = (NPC / 'NpcCombatAIService.luau').read_text()
        entering = ai.split('local function enterCombat(', 1)[1].split('local function returnHome(', 1)[0]
        self.assertLess(entering.index('agent.recovery:Cancel()'), entering.index('agent.target = target'))
        self.assertIn('CombatStateService.Activate(agent.model)', entering)
        unbind = ai.split('function NpcCombatAIService.Unbind(', 1)[1].split('function NpcCombatAIService.Start(', 1)[0]
        self.assertIn('agent.recovery:Cancel()', unbind)
        self.assertIn('agent.serial += 1', unbind)
        spawner = (NPC / 'NpcSpawnerService.luau').read_text()
        self.assertIn('NpcCombatAIService.Unbind(entity)', spawner)

    def test_return_uses_walk_and_chase_uses_run(self):
        ai = (NPC / 'NpcCombatAIService.luau').read_text()
        return_home = ai.split('local function returnHome(', 1)[1].split('local function attackCanConnect(', 1)[0]
        self.assertIn('NpcMovementPolicy.SpeedFor(agent.model:GetAttribute("RunSpeed"), "Peace")', return_home)
        tick = ai.split('local function tickAgent(', 1)[1].split('local function onDamage(', 1)[0]
        self.assertIn('NpcMovementPolicy.SpeedFor(agent.model:GetAttribute("RunSpeed"), "Combat")', tick)
        self.assertIn('NpcMovementPolicy.ModeFor("Combat")', ai)
        self.assertIn('policy.runSpeedMultiplier', ai)  # authored attack-speed multiplier retained
        self.assertIn('movementSlot = "walk"', ai)  # missing Run clip fallback only

    def test_presentation_owns_only_clips_and_no_pathing_or_state_decisions(self):
        presentation = (NPC / 'NpcAnimationService.luau').read_text()
        locomotion = (NPC / 'NpcLocomotionPresentation.luau').read_text()
        self.assertIn('NpcLocomotionPresentation.new(entity, animator, profile, weaponSet)', presentation)
        self.assertIn('locomotion:Play(NpcMovementPolicy.ModeFor("Peace"))', presentation)
        self.assertIn('locomotion:Play(NpcMovementPolicy.ModeFor("Combat"))', presentation)
        self.assertIn('locomotion:Destroy()', presentation)
        self.assertIn('Tracks.PublishedRows(profile, "walk", weaponSet)', locomotion)
        self.assertIn('Tracks.PublishedRows(profile, "run", weaponSet)', locomotion)
        self.assertIn('if previous and previous ~= clip then Tracks.Stop(previous) end', locomotion)
        for forbidden in ('Navigator', 'MoveTo', 'DamageService', 'GetService("Players")', 'task.spawn'):
            self.assertNotIn(forbidden, locomotion)
        self.assertNotIn('NpcLocomotionPresentation', read('src/server/monster/MonsterSpawnerService.luau'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
