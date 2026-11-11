"""M283: regressions for the Studio *published-clip* retrieval boundary.

These are explicit source-contract checks; the Roblox Content API cannot be run
by offline Python. Studio edit-mode playback remains a required smoke test.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PREVIEW = (ROOT / 'system/studio-plugin/modules/StudioTimelinePreview.luau').read_text('utf8')
COMMAND = (ROOT / 'system/studio-plugin/modules/StudioTimelineEditorCommands.luau').read_text('utf8')
INSTALL = (ROOT / 'system/studio-plugin/install.ps1').read_text('utf8')


class TimelineClipFetchM283(unittest.TestCase):
    def test_retry_is_bounded_and_always_validates_loaded_keyframe_data(self):
        self.assertIn('local MAX_CLIP_FETCHES = 5', PREVIEW)
        self.assertIn('for attempt = 1, MAX_CLIP_FETCHES do', PREVIEW)
        self.assertIn('AnimationClipProvider:GetAnimationClipAsync(contentId)', PREVIEW)
        self.assertIn('if duration > 0.000001 and poseCount > 0 then', PREVIEW)
        self.assertIn('task.wait(CLIP_RETRY_SECONDS)', PREVIEW)
        self.assertIn('last keyframe=%.6fs, loaded length=%.6fs', PREVIEW)
        self.assertLess(PREVIEW.index('timelineSequenceDetails(clip)'), PREVIEW.index('return clip'))
        self.assertIn('clip:Destroy()', PREVIEW)
        self.assertIn('No hit events were changed.', PREVIEW)
        self.assertNotIn('return timelineEditor.duration', PREVIEW)

    def test_non_keyframe_clip_is_not_reported_as_empty(self):
        self.assertIn('if not clip:IsA("KeyframeSequence") then', PREVIEW)
        self.assertIn('not KeyframeSequence; the timeline pose preview does not yet support this clip format', PREVIEW)
        self.assertNotIn('KeyframeSequenceProvider', PREVIEW)
        self.assertIn("'KeyframeSequenceProvider'", INSTALL)

    def test_unusable_clip_does_not_leave_old_session_or_partially_built_preview(self):
        loading = COMMAND.index('local sequence = loadTimelineSequence(animationAssetId)')
        preview = COMMAND.index('preview = loadTimelinePreviewModel(modelAssetId)')
        self.assertLess(loading, preview)
        self.assertIn('sequence:Destroy()', COMMAND)
        self.assertIn('destroyTimelinePreview()\n            timelineEditor.sessionId = ""', COMMAND)
        self.assertIn('result.error = firstLine:match', COMMAND)
        self.assertIn('warn("[game1 plugin] timeline editor failed: " .. tracebackText)', COMMAND)
        self.assertIn('if #tracks == 0 then', COMMAND)
        self.assertIn('No hit events were changed.', PREVIEW)
        self.assertLess(COMMAND.index('if #tracks == 0 then'), COMMAND.index('action = "ready"'))

    def test_no_changes_to_editor_protocol_or_live_combat(self):
        self.assertIn('schemaVersion = 1', COMMAND)
        self.assertIn('action = "set-event"', COMMAND)
        self.assertIn('action = "ready"', COMMAND)
        self.assertIn('result.animatedTargets = #timelineEditor.poseTracks', COMMAND)


if __name__ == '__main__':
    unittest.main()
