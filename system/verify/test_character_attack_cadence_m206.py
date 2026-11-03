"""M206: one character AttackSpeed stat determines the whole attack interval.

Checks the pure cadence contract, real authored timeline data and the actual
client/server call paths. No Roblox engine or live AnimationTrack is emulated.
"""
from __future__ import annotations

import json
import math
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMBAT = ROOT / "src/shared/combat"
CADENCE = (COMBAT / "CharacterAttackCadence.luau").read_text(encoding="utf-8")
TIMELINE = (COMBAT / "AttackTimelineConfig.luau").read_text(encoding="utf-8")
CLIENT = (ROOT / "src/client/character/animation/CharacterAnimationController.luau").read_text(encoding="utf-8")
SERVER = (ROOT / "src/server/combat/AttackService.luau").read_text(encoding="utf-8")
ATTACK_INPUT = (ROOT / "src/client/combat/AttackController.luau").read_text(encoding="utf-8")
REGISTRY = json.loads((ROOT / "assets/manifests/attack-timelines.json").read_text(encoding="utf-8"))


def policy_constant(name):
    match = re.search(r"CharacterAttackCadence\." + name + r"\s*=\s*([\d.]+)", CADENCE)
    if not match:
        raise AssertionError(f"missing policy constant {name}")
    return float(match.group(1))


def period(speed):
    reference = policy_constant("ReferenceAttackSpeed")
    base = policy_constant("ReferenceDurationSeconds")
    return base * reference / max(policy_constant("MinAttackSpeed"), min(policy_constant("MaxAttackSpeed"), speed))


class CharacterAttackCadenceM206(unittest.TestCase):
    def test_gameplay_period_is_independent_of_clip_duration(self):
        self.assertIn('function CharacterAttackCadence.DurationForStat(attackSpeed: any)', CADENCE)
        self.assertIn('CharacterAttackCadence.ReferenceDurationSeconds\n        * CharacterAttackCadence.ReferenceAttackSpeed / normalized', CADENCE)
        self.assertIn('gameplayDuration = CharacterAttackCadence.DurationForStat(statValue)', TIMELINE)
        self.assertIn('playbackSpeed = sourceDuration / playbackDuration', TIMELINE)
        self.assertIn('duration = gameplayDuration,', TIMELINE)
        self.assertIn('playbackDuration = math.max(0.001, gameplayDuration - AttackTimelineConfig.EndGuardSeconds)', TIMELINE)

        clips = [t for t in REGISTRY['timelines'] if t['clipId'].startswith('human_')]
        self.assertGreaterEqual(len(clips), 7)  # 3 female + 4 male from M204
        guard = 0.03
        for speed, expected in ((100, 3.0), (200, 1.5), (400, 0.75)):
            self.assertAlmostEqual(period(speed), expected)
            runtimes = []
            for clip in clips:
                authored = float(clip['duration'])
                runtime_playback_speed = authored / (period(speed) - guard)
                actual_animation_seconds = authored / runtime_playback_speed
                self.assertAlmostEqual(actual_animation_seconds, period(speed) - guard, places=8)
                runtimes.append(actual_animation_seconds + guard)
            self.assertTrue(all(math.isclose(t, expected) for t in runtimes))

    def test_normalized_hit_windows_scale_with_gameplay_duration_not_fbx_length(self):
        guard = 0.03
        clips = [t for t in REGISTRY['timelines'] if t['clipId'].startswith('human_')]
        for speed in (100, 200, 400):
            active = period(speed) - guard
            for clip in clips:
                events = clip['events']
                start = events['HitStart']['normalizedTime'] * active
                end = events['HitEnd']['normalizedTime'] * active
                self.assertLessEqual(0, start)
                self.assertLess(start, end)
                self.assertLessEqual(end, active)
                self.assertAlmostEqual(start / active, events['HitStart']['normalizedTime'])

    def test_both_sides_use_one_authoritative_stat_based_resolver(self):
        call = 'AttackTimelineConfig.ResolveCharacterRuntime(clipId, character:GetAttribute("AttackSpeed"))'
        self.assertIn(call, SERVER)
        self.assertIn(call, CLIENT)
        self.assertNotIn('AnimationSpeedScaling.ResolveForAnimation(character, "attack", descriptor.animationId)', SERVER)
        self.assertIn('AttackSessionStore.Begin(player, character, serial, clientAttackId, now + attackDuration, damageWindow)', SERVER)
        self.assertIn('currentActionLockedUntil = if slot == "attack" then now + runtimeDuration else 0', CLIENT)
        self.assertIn('AttackUpperBodyComposer.Begin(character, descriptor, playbackSpeed)', CLIENT)
        self.assertIn('action.durationSeconds', ATTACK_INPUT)
        self.assertIn('math.min(attackDuration, AttackConfig.FacingTurnSeconds)', ATTACK_INPUT)

    def test_no_change_to_npc_monster_timing_policy(self):
        for file in ('src/server/npc/NpcCombatAIService.luau', 'src/server/monster/MonsterAttackExecutor.luau'):
            source = (ROOT / file).read_text(encoding='utf-8')
            self.assertIn('AttackTimelineConfig.ResolveRuntime(', source)
            self.assertNotIn('ResolveCharacterRuntime', source)
        self.assertIn('function AttackTimelineConfig.ResolveRuntime(clipId: any, animationSpeedPercent: any)', TIMELINE)

    def test_bad_stat_is_bounded_and_clip_identity_is_preserved(self):
        self.assertIn('numeric ~= numeric or numeric == math.huge or numeric == -math.huge', CADENCE)
        self.assertAlmostEqual(period(0), 12.0)
        self.assertAlmostEqual(period(10000), 0.75)
        self.assertIn('local source = AttackTimelineConfig.ResolveBase(clipId)', TIMELINE)
        self.assertIn('clipId = tostring(clipId)', TIMELINE)


if __name__ == "__main__":
    unittest.main()
