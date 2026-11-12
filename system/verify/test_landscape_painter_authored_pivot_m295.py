"""M295: Landscape Painter must preserve the published FBX/rig pivot.

These contracts compare Landscape placement to DecoManager's shared transform,
not a simulated Roblox Studio physics or imported-rig smoke test.
"""
from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[2]
LAND = ROOT / "system/landscape-plugin"


def src(filename):
    return (LAND / filename).read_text(encoding="utf-8")


class LandscapeAuthoredPivotM295(unittest.TestCase):
    def test_deco_transform_is_reused_from_single_source(self):
        aliases = json.loads(src("plugin.project.json"))["tree"]["modules"]
        self.assertEqual(aliases["DecoTransform"]["$path"],
                         "../studio-plugin/modules/DecoTransform.luau")
        self.assertTrue((LAND / aliases["DecoTransform"]["$path"]).resolve().is_file())
        self.assertIn('require(script.Parent.DecoTransform)',
                      src('modules/LandscapeSurface.luau'))
        self.assertIn('require(script.Parent.DecoTransform)',
                      src('modules/LandscapeAssetPlacement.luau'))

    def test_surface_contact_preserves_original_geometry_to_pivot_offset(self):
        surface = src('modules/LandscapeSurface.luau')
        self.assertIn('point + normal.Unit * supportOffset', surface)
        self.assertIn('DecoTransform.placementPivot(authoredRotation,', surface)
        self.assertIn('elseif targetKind == "surface" then', surface)
        self.assertIn('point - Vector3.yAxis * settings.length', surface)
        self.assertIn('else point', surface)  # authored-stem socket uses the pivot
        self.assertNotIn('model.WorldPivot =', surface)
        self.assertNotIn('PivotOffset =', surface)
        self.assertNotIn('model.PrimaryPart =', surface)

    def test_preview_and_placement_use_one_authored_frame(self):
        placement = src('modules/LandscapeAssetPlacement.luau')
        self.assertIn('DecoTransform.authoredPivotRotation(model)', placement)
        self.assertIn('DecoTransform.supportOffset(model)', placement)
        self.assertIn('self.authoredPivotRotation = rotation', placement)
        self.assertIn('self.authoredSupportOffset = support', placement)
        self.assertIn('self.cursor.pivot = pivot', placement)
        self.assertIn('local pivot = cursor.pivot', placement)
        self.assertIn('ghost:PivotTo(pivot)', placement)
        self.assertIn('instance:PivotTo(pivot)', placement)
        self.assertNotIn('instance.PrimaryPart =', placement)
        self.assertNotIn('instance.WorldPivot =', placement)
        self.assertNotIn('instance.PivotOffset =', placement)

    def test_visual_tether_endpoint_remains_author_pivot(self):
        placement = src('modules/LandscapeAssetPlacement.luau')
        sway = src('modules/LandscapeSwayAuthoring.luau')
        self.assertIn('makeTether(instance, cursor.point, pivot.Position, config)', placement)
        self.assertIn('SwayAuthoring.Sync(instance, config)', placement)
        self.assertIn('local pivot = model:GetPivot()', sway)
        self.assertNotIn('part.PivotOffset =', sway)

    def test_apply_uses_saved_authored_pose_and_migrates_only_with_original(self):
        placement = src('modules/LandscapeAssetPlacement.luau')
        for key in ('LandscapeAuthoredPivotRotation',
                    'LandscapeAuthoredSupportOffset', 'LandscapeFacingDirection'):
            self.assertIn('model:SetAttribute("' + key + '"', placement)
            self.assertIn('model:GetAttribute("' + key + '")', placement)
        self.assertIn('"LandscapeSchemaVersion", 3', placement)
        self.assertIn('tostring(self.row.model_asset_id) ~= tostring(model:GetAttribute("LandscapeModelAssetId"))', placement)
        self.assertIn('Старое размещение:', placement)
        self.assertIn('self.history:FinishRecording(record, Enum.FinishRecordingOperation.Cancel)', placement)
        self.assertIn('model:PivotTo(previousPivot)', placement)


if __name__ == '__main__':
    unittest.main()
