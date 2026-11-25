"""Loading travel is independent of the determinate and indeterminate fill."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
CLIENT = ROOT / 'src/client/character'

class LoadingRunner(unittest.TestCase):
    def test_travel_and_pose_share_elapsed_time(self):
        runner = (CLIENT / 'CharacterLoadingRunner.luau').read_text(encoding='utf8')
        self.assertIn('local LEG_SECONDS = 1', runner)
        self.assertIn('local phase = (elapsed / LEG_SECONDS) % 2', runner)
        self.assertIn('if phase < 1 then return phase, true end', runner)
        self.assertIn('return 2 - phase, false', runner)
        self.assertIn('local _, right = Runner.Travel(elapsed)', runner)
        self.assertIn('Vector2.new(Runner.Width - point.X, point.Y)', runner)
        self.assertIn('connectSegment(segment, facing(a), facing(b))', runner)
        self.assertIn('connect(torso, SHOULDER, HIP)', runner.split('local function pose')[1])
        self.assertIn('local headPoint = facing(Vector2.new(25, 7))', runner)
        self.assertIn('local nosePoint = facing(Vector2.new(29, 7))', runner)
        self.assertNotIn('UIScale', runner)

    def test_overlay_does_not_drive_runner_from_progress(self):
        panel = (CLIENT / 'CharacterCreationPanel.luau').read_text(encoding='utf8')
        self.assertIn('local runnerPosition = LoadingRunner.Travel(elapsed)', panel)
        self.assertIn('UDim2.new(runnerPosition, LoadingRunner.Width * (0.5 - runnerPosition)', panel)
        self.assertIn('views.overlayRunnerPose(elapsed)', panel)
        self.assertIn('views.overlayFill.Size = UDim2.new(if value ~= nil then value else 0.22', panel)
        self.assertIn('views.overlayFill.Position = UDim2.new(if value ~= nil then 0 else position * 0.78', panel)
        self.assertEqual(panel.count('RunService.RenderStepped:Connect(render)'), 1)
        self.assertIn('if not views.runnerConnection then\n        views.runnerStart = os.clock()', panel)

if __name__ == '__main__':
    unittest.main()
