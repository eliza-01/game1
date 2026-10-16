"""M70 contracts against M69: mimic monster attack ownership and return-gate semantics.

Source checks cannot assert real Roblox AnimationTrack playback; the Studio
validation is still required after applying this patch.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8-sig")


class NpcMonsterAttackContracts(unittest.TestCase):
    def test_monster_timeline_is_authoritative_and_npc_fallback_is_loaded_clip(self):
        npc = read("src/server/npc/NpcCombatAIService.luau")
        presentation = read("src/server/npc/NpcAnimationService.luau")
        timeline = read("src/shared/combat/AttackTimelineData.luau")
        registry = read("src/shared/npc/NpcAnimationRegistry.luau")
        self.assertIn('clipId = "npc__guard_01__attack__01"', registry)
        self.assertNotIn('["npc__guard_01__attack__01"]', timeline)
        self.assertIn('AttackTimelineConfig.ResolveRuntime(row.clipId, percent)', npc)
        self.assertIn('agent.presentation.StartAttack(row, percent)', npc)
        self.assertIn('length = finite(track.Length, 0)', npc)
        self.assertIn('length / speed', npc)
        self.assertIn('timeline.playbackDuration', npc)
        self.assertIn('length / speed', npc)
        self.assertIn('task.wait(0.05)', npc)
        self.assertIn('return true, if currentAttack then currentAttack.track else nil', presentation)

    def test_hit_does_not_end_clip_or_return_early(self):
        npc = read("src/server/npc/NpcCombatAIService.luau")
        attack = npc.split('local function beginAttack(', 1)[1].split('local function tickAgent(', 1)[0]
        hit = attack.split('task.delay(math.max(0, hitAt - elapsed)', 1)[1].split('task.delay(math.max(0, duration - elapsed)', 1)[0]
        completion = attack.split('task.delay(math.max(0, duration - elapsed)', 1)[1]
        self.assertIn('DamageService.Apply(', hit)
        self.assertIn('agent.returnAfterAttack = true', hit)
        self.assertNotIn('startReturn(', hit)
        self.assertNotIn('agent.presentation.EndAttack()', hit)
        self.assertIn('agent.presentation.EndAttack()', completion)
        self.assertIn('beginAttack(agent, target, true)', completion)
        self.assertIn('startReturn(agent, true)', completion)
        self.assertIn('if agent.attacking then return end', npc)
        self.assertIn('if agent.target == attacker then return end', npc)

    def test_return_state_blocks_special_until_home_pose_restored(self):
        npc = read("src/server/npc/NpcCombatAIService.luau")
        animation = read("src/server/npc/NpcAnimationService.luau")
        return_start = npc.split('local function startReturn(', 1)[1].split('local function enterCombat(', 1)[0]
        return_home = npc.split('local function returnHome(', 1)[1].split('local function attackCanConnect(', 1)[0]
        self.assertLess(return_start.index('SetReturnActive(true)'), return_start.index('clearTarget(agent)'))
        self.assertLess(return_home.index('agent.root.CFrame = agent.home'), return_home.index('SetReturnActive(false)'))
        self.assertIn('if returning then', animation)
        self.assertIn('idle:Stop()', animation.split('if returning then', 1)[1].split('elseif combatActive', 1)[0])
        self.assertIn('SetReturnActive = setReturnActive', animation)
        self.assertIn('SetReturnMoving = setReturnMoving', animation)

    def test_monster_attack_runtime_is_preserved(self):
        monster = read("src/server/monster/MonsterAttackExecutor.luau")
        service = read("src/server/monster/MonsterAIService.luau")
        self.assertIn('local function maintainAttackPursuit', monster)
        self.assertIn('local timing = AttackTimelineConfig.ResolveRuntime', monster)
        self.assertIn('function MonsterAttackExecutor.Begin(agent: any, target: Model', monster)
        self.assertIn('AttackExecutor.Begin(agent, target, AttackMovement, random)', service)


if __name__ == "__main__":
    unittest.main(verbosity=2)
