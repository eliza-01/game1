"""Contract/regression tests for the separate Game1 Landscape Painter M284.

Real cursor/raycast/published models need a manual Roblox Studio Edit session.
"""
from __future__ import annotations
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'system' / 'landscape-plugin'


def src(name):
    return (BASE / name).read_text('utf-8')


class LandscapeM284Tests(unittest.TestCase):
    def test_shared_deco_asset_loader_is_linked_not_duplicated(self):
        spec = json.loads(src('plugin.project.json'))['tree']['modules']
        names = {key: val['$path'] for key, val in spec.items() if key != '$className'}
        self.assertEqual(names['DecoAssetLoader'], '../studio-plugin/modules/DecoAssetLoader.luau')
        self.assertEqual(names['StudioSkinnedMeshConnection'], '../../src/shared/rig/SkinnedMeshConnection.luau')
        self.assertEqual(names['StudioMeshPhysicsCore'], '../../src/shared/world/MeshPhysicsCore.luau')
        self.assertIn('self.loader:fetchRegistry()', src('modules/LandscapeAssetCatalog.luau'))
        self.assertIn('self.loader:loadPublished(row)', src('modules/LandscapeAssetCatalog.luau'))
        self.assertIn('row.status == "PUBLISHED"', src('modules/LandscapeAssetCatalog.luau'))
        for path in names.values():
            self.assertTrue((BASE / path).resolve().is_file(), path)

    def test_surface_point_normal_and_pivot_control(self):
        surface = src('modules/LandscapeSurface.luau')
        self.assertIn('CFrame.lookAt(position, position + facing, up)', surface)
        self.assertIn('normal.Unit * offset', surface)
        self.assertIn('Enum.RaycastFilterType.Exclude', surface)
        self.assertIn('table.insert(ignore, decor)', surface)
        self.assertIn('table.insert(ignore, camera)', surface)
        self.assertIn('settings.tetherEnabled', surface)

    def test_single_generator_for_stems_and_tethers(self):
        original = src('modules/BranchPlacement.luau')
        tether = src('modules/LandscapeAssetPlacement.luau')
        self.assertIn('BranchGeometry.CreateSegments', original)
        self.assertIn('BranchGeometry.Apply(line, hitPoint, targetPoint', tether)
        self.assertIn('LINE_NAME = "LandscapeAttachmentLine"', tether)
        self.assertIn('self.preview:Show(anchors', tether)
        self.assertIn('Surface.Pivot(hit.Position, hit.Normal, config)', tether)
        self.assertNotIn('Instance.new("WeldConstraint")', tether)

    def test_use_and_apply_are_separate_and_persistent(self):
        profiles = src('modules/LandscapeProfiles.luau')
        self.assertIn('self.plugin:SetSetting(KEY, self.data)', profiles)
        self.assertIn('self.data.activeId = id', profiles)
        self.assertIn('settings.id = item.id', profiles)
        self.assertIn('MAX_PROFILES = 60', profiles)
        self.assertIn('Profiles.Validate', profiles)
        placement = src('modules/LandscapeAssetPlacement.luau')
        self.assertIn('self.profiles:List()', placement)
        self.assertIn('self.profiles:Find(activeId)', placement)
        self.assertIn('function Placement:ApplyToSelection(config)', placement)
        self.assertIn('selection:Get()', placement)
        self.assertIn('LandscapeSurfacePoint', placement)
        self.assertIn('LandscapeSurfaceNormal', placement)
        self.assertIn('model:PivotTo', placement)
        self.assertIn('if not managed and config.tetherEnabled then', placement)

    def test_undo_and_transient_preview(self):
        placement = src('modules/LandscapeAssetPlacement.luau')
        self.assertIn('TryBeginRecording', placement)
        self.assertIn('Enum.FinishRecordingOperation.Cancel', placement)
        self.assertIn('Enum.FinishRecordingOperation.Commit', placement)
        self.assertIn('clone.Archivable = false', placement)
        self.assertIn('clone.Parent = self.workspace.CurrentCamera', placement)
        self.assertIn('self:HideGhost()', placement)
        self.assertIn('instance.Parent = folder', placement)
        self.assertIn('LandscapeModelAssetId', placement)
        self.assertIn('function Placement:Destroy()', placement)
        main = src('LandscapePainter.server.luau')
        self.assertIn('RunService:IsRunning()', main)
        self.assertIn('plugin.Unloading', main)
        self.assertIn('plugin.Deactivation', main)
        self.assertIn('Enum.KeyCode.Return', main)

    def test_profile_ui_has_separate_use_apply_and_tether_params(self):
        ui = src('modules/LandscapeAssetsWidget.luau')
        self.assertIn('Use ·', ui)
        self.assertIn('Apply · к выделенной Model', ui)
        self.assertIn('Сохранить новый профиль', ui)
        self.assertIn('self.config.tetherEnabled', ui)
        self.assertIn('self.config.color', ui)
        self.assertIn('self.config.length', ui)
        self.assertIn('self.config.thickness', ui)
        self.assertIn('self.actions.selectAsset(row)', ui)


if __name__ == '__main__':
    unittest.main()
