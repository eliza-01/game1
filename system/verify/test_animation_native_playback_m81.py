"""Native playback contracts for Character, NPC and Monster animation loops."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class NativeAnimationPlaybackTests(unittest.TestCase):
    def test_npc_has_one_playback_track_per_clip_and_keeps_time_on_speed_change(self):
        tracks = source("src/server/npc/NpcAnimationTracks.luau")
        self.assertEqual(tracks.count("animator:LoadAnimation(animation)"), 1)
        self.assertIn("if clip.track.IsPlaying then", tracks)
        self.assertIn("clip.track:AdjustSpeed(speed)", tracks)
        self.assertIn("clip.track:Play(fade or NpcConfig.TransitionSeconds, 1, speed)", tracks)
        self.assertIn("clip.track:Stop(fade or NpcConfig.TransitionSeconds)", tracks)

    def test_idle_cycles_use_native_events_without_extra_pose_tracks(self):
        npc = source("src/server/npc/NpcIdlePresentation.luau")
        monster = source("src/server/monster/MonsterIdlePresentation.luau")
        self.assertIn("self.base.track.DidLoop:Connect", npc)
        self.assertIn("clip.track.Stopped:Connect", npc)
        self.assertIn("Tracks.SecondsRemaining(special)", npc)
        self.assertIn("registerSignal(idleTrack.DidLoop, function()", monster)
        self.assertIn("registerSignal(choice.track.Ended, function()", monster)
        self.assertIn("playTrackAtConfiguredSpeed(model, choice.track", monster)

    def test_character_prewarms_single_track_and_death_hold_is_preserved(self):
        cache = source("src/client/character/animation/AnimationTrackCache.luau")
        controller = source("src/client/character/animation/CharacterAnimationController.luau")
        self.assertIn('loadTrack(self, descriptor, "primary", "")', cache)
        self.assertIn("table.insert(tracks, track)", cache)
        self.assertIn("nextTrack:Play(0.15, 1, playbackScale)", controller)
        self.assertIn("RunService.PreAnimation:Connect(maintainDeathPose)", controller)
        self.assertIn("maintainDeathTerminalPose(deltaTimeSim)", controller)


if __name__ == "__main__":
    unittest.main()
