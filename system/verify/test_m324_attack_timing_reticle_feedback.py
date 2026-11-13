"""M324: real loaded attack source length and melee raycast-only miss policy.

Roblox AnimationTrack.Length is unavailable outside Studio; the timing tests
model the deterministic scaling relation and source wiring, not rendered poses.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def source(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


def outcome(*, is_bow, pursued, aimed_state, damaged_targets):
    if damaged_targets:
        return None
    if aimed_state == 'out_of_range_monster':
        return 'far'
    if aimed_state == 'in_range' or (is_bow and pursued):
        return 'miss'
    return None


def incoming_miss_allowed(attack_ends, now, weapon):
    return not (attack_ends is not None and attack_ends > now and weapon != 'bow')


class AttackTimingTests(unittest.TestCase):
    def test_real_clip_length_never_creates_terminal_gap(self):
        gameplay_seconds = 3.0
        playback_duration = 2.97
        authored_duration = 1.5
        for actual_track_length in (0.83, 1.1, 1.5, 1.87, 2.3):
            # Old speed authored_duration/playback_duration freezes an early-ending
            # track for as long as ~1 second when the published clip is shorter.
            speed = actual_track_length / playback_duration
            self.assertAlmostEqual(actual_track_length / speed, playback_duration)
            self.assertLess(gameplay_seconds - actual_track_length / speed, 0.04)
        self.assertGreater(playback_duration - 1.1 / (authored_duration / playback_duration), 0.7)

    def test_client_consumes_loaded_speed_and_preserves_server_cadence(self):
        composer = source('src/client/character/animation/AttackUpperBodyComposer.luau')
        controller = source('src/client/character/animation/CharacterAnimationController.luau')
        timeline = source('src/shared/combat/AttackTimelineConfig.luau')
        server = source('src/server/combat/AttackService.luau')
        self.assertIn('track.Length / playbackDuration', composer)
        self.assertIn('return track, nil, sourcePlaybackSpeed', composer)
        self.assertIn('end, timeline.playbackDuration)', controller)
        self.assertIn('playbackSpeed = loadedPlaybackSpeed or playbackSpeed', controller)
        self.assertIn('timeline.playbackSpeed = playbackSpeed', controller)
        self.assertIn('tonumber(timeline and timeline.playbackSpeed)', controller)
        self.assertIn('sourceTrack:AdjustSpeed(sourcePlaybackSpeed)', composer)
        self.assertIn('gameplayDuration = CharacterAttackCadence.DurationForStat(statValue)', timeline)
        self.assertIn('local attackDuration = timing.duration', server)
        self.assertNotIn('track.Length / playbackDuration', server)


class MeleeFeedbackTests(unittest.TestCase):
    def test_miss_requires_ray_target_and_zero_aggregate_damage(self):
        self.assertIsNone(outcome(is_bow=False, pursued=True, aimed_state=None, damaged_targets=0))
        self.assertIsNone(outcome(is_bow=False, pursued=True, aimed_state='in_range', damaged_targets=1))
        self.assertIsNone(outcome(is_bow=False, pursued=True, aimed_state='in_range', damaged_targets=3))
        self.assertEqual(outcome(is_bow=False, pursued=False, aimed_state='in_range', damaged_targets=0), 'miss')
        self.assertEqual(outcome(is_bow=False, pursued=True, aimed_state='out_of_range_monster', damaged_targets=0), 'far')
        self.assertEqual(outcome(is_bow=True, pursued=True, aimed_state=None, damaged_targets=0), 'miss')

    def test_incoming_enemy_misses_do_not_overlay_our_melee_attack(self):
        self.assertFalse(incoming_miss_allowed(attack_ends=12.0, now=11.5, weapon='1hs'))
        self.assertFalse(incoming_miss_allowed(attack_ends=12.0, now=11.5, weapon='hands'))
        self.assertTrue(incoming_miss_allowed(attack_ends=12.0, now=11.5, weapon='bow'))
        self.assertTrue(incoming_miss_allowed(attack_ends=12.0, now=12.1, weapon='1hs'))
        policy = source('src/shared/combat/AttackFeedbackPolicy.luau')
        service = source('src/server/combat/CombatFeedbackService.luau')
        self.assertIn('if aimedState == "in_range" or (isBow and pursued) then', policy)
        self.assertIn('Policy.AllowIncomingMiss(', service)
        self.assertIn('Policy.Resolve(HostilePursuitRegistry.IsPursued(character), aimedState, isBow)', service)

    def test_authoritative_attack_outcome_is_once_per_session(self):
        attack = source('src/server/combat/AttackService.luau')
        session = source('src/server/combat/AttackSessionStore.luau')
        targeting = source('src/server/combat/AttackFeedbackTargeting.luau')
        self.assertIn('if reportMiss and not finished.damageDealt', attack)
        self.assertIn('AttackSessionStore.Finish(player, character, serial, clientAttackId)', attack)
        self.assertIn('if damagedTargets > 0 then', attack)
        self.assertIn('session.damageDealt = true', session)
        self.assertIn('EntityHitboxService.RaycastAimRegions(', targeting)
        self.assertIn('not unobstructed(character, candidate.model, origin, candidate.hitPosition)', targeting)
        self.assertEqual(attack.count('CombatFeedbackService.PublishAttackOutcome('), 2)


if __name__ == '__main__':
    unittest.main()
