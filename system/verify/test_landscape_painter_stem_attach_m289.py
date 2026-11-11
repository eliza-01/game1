"""Static contracts and migration guarantees for M289; Roblox Edit smoke still required."""
from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'system' / 'landscape-plugin'

def src(name):
    return (BASE / name).read_text(encoding='utf-8')

class StemAttachContract(unittest.TestCase):
    def test_target_module_and_plugin_mapping(self):
        project = json.loads(src('plugin.project.json'))['tree']['modules']
        self.assertEqual(project['LandscapeStemTarget']['$path'], 'modules/LandscapeStemTarget.luau')
        target = src('modules/LandscapeStemTarget.luau')
        self.assertIn('StemTarget.Closest(', target)
        self.assertIn('StemTarget.IsAuthoredStem(', target)
        self.assertIn('StemTarget.Collect(', target)
        self.assertIn('CanQuery=false', target)
        self.assertIn('part.Name:match("^Stem_%d+$")', target)
        self.assertIn('part.CFrame.RightVector', target)
        self.assertIn('stopDistance', target)

    def test_surface_raycast_untouched_and_target_modes(self):
        self.assertIn('table.insert(ignore, decor)', src('modules/LandscapeSurface.luau'))
        placement = src('modules/LandscapeAssetPlacement.luau')
        self.assertIn('self.targetMode = "auto"', placement)
        self.assertIn('StemTarget.Find(', placement)
        self.assertIn('if self.targetMode == "surface" then return surface', placement)
        self.assertIn('if self.targetMode == "stem" then return nil', placement)
        self.assertIn('self:ScanStems(true)', placement)
        ui = src('modules/LandscapeAssetsWidget.luau')
        self.assertIn('Прицел: Только стебель', ui)
        self.assertIn('Прицел: Только поверхность', ui)
        self.assertIn('targetModeChanged', ui)
        self.assertIn('assets:SetTargetMode(mode)', src('LandscapePainter.server.luau'))

    def test_old_stems_remain_pickable_and_new_normals_are_saved(self):
        target = src('modules/LandscapeStemTarget.luau')
        self.assertIn('branch:GetAttribute("StartNormal")', target)
        self.assertIn('branch:GetAttribute("EndNormal")', target)
        self.assertIn('part:GetAttribute("LandscapeStemNormalA")', target)
        geometry = src('modules/BranchGeometry.luau')
        self.assertIn('part.CanQuery = false', geometry)
        self.assertIn('part:SetAttribute("LandscapeStemNormalA"', geometry)
        self.assertIn('part:SetAttribute("LandscapeStemNormalB"', geometry)
        self.assertEqual(geometry.count('function BranchGeometry.Apply'), 1)

    def test_asset_lifecycle_and_reapply_does_not_lie_about_attaching(self):
        placement = src('modules/LandscapeAssetPlacement.luau')
        self.assertIn('ObjectValue', placement)
        self.assertIn('LandscapeAnchorStem', placement)
        self.assertIn('LandscapeStemLocalPoint', placement)
        self.assertIn('LandscapeStemLocalNormal', placement)
        self.assertIn('STEM_ATTACHMENTS_NAME = "Attachments"', placement)
        self.assertIn('instance.Parent = attachToStem(instance, cursor)', placement)
        self.assertIn('instance.Parent = folder', placement)
        self.assertIn('model:IsDescendantOf(branch)', placement)
        self.assertIn('link.Value.CFrame:PointToWorldSpace(localPoint)', placement)
        self.assertIn('Enum.FinishRecordingOperation.Cancel', placement)
        self.assertNotIn('Instance.new("WeldConstraint")', placement)

    def test_other_pipeline_untouched(self):
        main = src('LandscapePainter.server.luau')
        self.assertIn('RunService:IsRunning()', main)
        self.assertIn('plugin.Unloading', main)

if __name__ == '__main__': unittest.main()
