"""M101 Studio Timeline package, authority and compatibility contracts.

These do not replace a Studio edit-mode smoke test (viewport interaction/asset loading).
"""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "system/studio-plugin"
MAIN = (PLUGIN / "Game1Bridge.server.luau").read_text(encoding="utf-8")
NAMES = (
    "StudioTimelineEditorCommands", "StudioTimelineWidget", "StudioTimelinePreview",
    "StudioTimelinePoseSampler", "StudioTimelineTransport",
)
SOURCES = {n: (PLUGIN / "modules" / f"{n}.luau").read_text(encoding="utf-8") for n in NAMES}
PROJECT = json.loads((PLUGIN / "plugin.project.json").read_text(encoding="utf-8"))


class TimelineDecompositionM101(unittest.TestCase):
    def test_modules_are_explicit_rojo_siblings(self):
        for name in NAMES:
            with self.subTest(module=name):
                self.assertEqual(PROJECT["tree"]["modules"][name]["$path"], f"modules/{name}.luau")
        for name in NAMES[1:]:
            self.assertIn(f"require(script.Parent.{name})", SOURCES[NAMES[0]])
        self.assertIn('require(script.Parent.modules.StudioTimelineEditorCommands)', MAIN)

    def test_main_is_thin_composition_root_and_retains_edit_mode_gate(self):
        self.assertLess(len(MAIN.splitlines()), 200)
        self.assertIn('StudioTimelineEditorCommands({', MAIN)
        self.assertIn('if RunService:IsRunning() then', MAIN)
        self.assertIn('elseif data.command == "timeline-editor" then', MAIN)
        self.assertIn('handleTimelineEditor(data)', MAIN)
        for fragment in ('Instance.new("ViewportFrame")', 'local function sampleTimelineTrack',
                         'local function postTimelineAgent', 'local function handleTimelineEditor('):
            self.assertNotIn(fragment, MAIN)
        self.assertIn('data.command == "model-load"', MAIN)
        self.assertIn('data.command == "monster-spawn"', MAIN)
        self.assertIn('data.command == "location-authoring"', MAIN)

    def test_session_validation_event_catalog_and_errors_are_preserved(self):
        source = SOURCES['StudioTimelineEditorCommands']
        for marker in (
            'tonumber(data.schemaVersion) ~= 1', 'sessionId == ""',
            'modelAssetId <= 0', 'animationAssetId <= 0',
            'timelineEditor.eventCatalog', 'timelineEditor.events',
            'poseSampler.Build(preview, sequence)', 'poseSampler.Apply(timelineEditor.poseTracks,',
            'action = "ready"', 'action = "set-event"',
            '"ViewportFrame/TimelinePreviewWorld/" .. TIMELINE_PREVIEW_NAME',
            'result.animatedTargets = #timelineEditor.poseTracks',
            'pcall(postTimelineEditorResult, result)', 'debug.traceback',
            'return handleTimelineEditor',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)
        self.assertLess(source.index('destroyTimelinePreview()'), source.index('local preview = loadTimelinePreviewModel'))

    def test_pose_sampler_preserves_target_mapping_and_easing(self):
        source = SOURCES['StudioTimelinePoseSampler']
        for marker in (
            'target:IsA("Bone")', 'target:IsA("Motor6D")',
            'candidate.Part0.Name == parentPose.Name',
            'table.sort(keyframes', 'table.sort(track.samples',
            'styleName == "Constant"', 'TweenService:GetValue(alpha, style, direction)',
            'return track.defaultTransform:Lerp(samples[1].cframe, alpha)',
            'current.cframe:Lerp(following.cframe, alpha)',
            'setTimelineTargetTransform(track.target, sampleTimelineTrack(track, timePosition))',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)
        self.assertNotIn('HttpService', source)
        self.assertNotIn('Workspace', source)

    def test_preview_keeps_isolated_world_and_bound_loading_retries(self):
        source = SOURCES['StudioTimelinePreview']
        for marker in (
            'AssetService:LoadAssetAsync(assetId)', 'for _ = 1, 6 do',
            'AnimationClipProvider:GetAnimationClipAsync(contentId)', 'for _ = 1, 4 do',
            'clip:IsA("KeyframeSequence")', 'prepareTimelinePreviewModel(preview)',
            'preview.Parent = timelineWorld', 'timelineViewportEmpty.Visible = false',
            'activePreview:Destroy()', 'timelineWorld:GetChildren()',
            'timelineViewport.InputChanged:Connect', 'timelineViewport.InputEnded:Connect',
            'UserInputService.InputEnded:Connect',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)
        self.assertNotIn('preview.Parent = Workspace', source)
        self.assertNotIn('AnimationTrack', source)

    def test_widget_has_persistent_id_and_original_events(self):
        source = SOURCES['StudioTimelineWidget']
        for marker in (
            '"Game1AttackTimeline_v2"', '"TimelinePreviewWorld"',
            'Instance.new("ViewportFrame")', 'Instance.new("WorldModel")',
            '"Confirm point"', '"Scrubber"', '"EventButtons"',
            'eventButtons = timelineEventButtons', 'confirm = timelineConfirm',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)
        self.assertNotIn('HttpService', source)

    def test_transport_keeps_protocol_and_rejection_semantics(self):
        source = SOURCES['StudioTimelineTransport']
        for marker in (
            'AGENT_BASE_URL .. "/api/timelines/editor-event"',
            'BRIDGE_URL .. "/timeline-editor-result"',
            '["X-Control-Token"] = AGENT_TOKEN',
            '["X-Game1-Token"] = BRIDGE_TOKEN',
            'if not response.Success then',
            'PostAgent = postTimelineAgent', 'PostResult = postTimelineEditorResult',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)
        self.assertNotIn('Instance.new', source)

    def test_installer_rejects_missing_module_in_bundle(self):
        source = (PLUGIN / 'install.ps1').read_text(encoding='utf-8')
        for name in NAMES:
            self.assertIn(f"'{name}'", source)
        self.assertIn('Get-FileHash $Installed -Algorithm SHA256', source)


if __name__ == '__main__':
    unittest.main()
