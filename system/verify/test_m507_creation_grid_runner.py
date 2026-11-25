"""UI contracts; actual GUI joint placement is covered by the Studio smoke test."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
CLIENT = ROOT / 'src/client/character'


class CreationGridRunner(unittest.TestCase):
    def test_four_columns_dynamic_height_and_width(self):
        picker = (CLIENT/'CharacterCreationAppearanceView.luau').read_text(encoding='utf8').split('local function materialPicker(')[1]
        for fragment in ('local columns, cellHeight, gap = 4, 46, 8',
                         'math.ceil(#materials / columns)', 'rows * cellHeight + (rows - 1) * gap',
                         '52 + gridHeight', 'grid.FillDirectionMaxCells = columns',
                         'list:GetPropertyChangedSignal("AbsoluteSize"):Connect(resizeCells)',
                         'math.floor((width - (columns - 1) * gap) / columns)',
                         'list.Visible = true', 'item.Activated:Connect(function() pick(material) end)'):
            self.assertIn(fragment, picker)

    def test_runner_joint_connections_and_lifecycle(self):
        runner = (CLIENT/'CharacterLoadingRunner.luau').read_text(encoding='utf8')
        panel = (CLIENT/'CharacterCreationPanel.luau').read_text(encoding='utf8')
        for fragment in ('connect(arm, SHOULDER, elbow)', 'connect(forearm, elbow, hand)',
                         'connect(thigh, HIP, knee)', 'connect(shin, knee, foot)',
                         'side(phase + math.pi', 'math.atan2(-delta.X, delta.Y)',
                         'local centre = (a + b) * 0.5', 'pose(0)'):
            self.assertIn(fragment, runner)
        self.assertIn('views.overlayRunnerPose(elapsed)', panel)
        self.assertIn('views.runnerConnection:Disconnect()', panel)
        self.assertNotIn('local function setRunnerPose(', panel)
        self.assertNotIn('"Sword"', runner)


if __name__ == '__main__':
    unittest.main()
