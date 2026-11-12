"""M296: published rig_carrier's native pivot belongs to the imported mesh.

Source contracts protect both editor tools. The numeric test demonstrates why
an outer Model/RootPart pivot may not be copied into a MeshPart.PivotOffset.
Roblox Edit-mode integration remains a required manual smoke test.
"""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
STUDIO = ROOT / "system/studio-plugin"
LANDSCAPE = ROOT / "system/landscape-plugin"


class NativeRigPivotM296(unittest.TestCase):
    def test_loader_preserves_native_part_offset_and_uses_it_as_model_pivot(self):
        source = (STUDIO / "modules/DecoAssetLoader.luau").read_text("utf-8")
        self.assertIn("PublishedRigNormalize.Apply(model, row.rigManifest)", source)
        self.assertIn("local nativeCarrierPivot = carrier:GetPivot()", source)
        self.assertIn("local nativeCarrierOffset = carrier.PivotOffset", source)
        self.assertIn("model.PrimaryPart = carrier", source)
        self.assertIn("carrier.PivotOffset ~= nativeCarrierOffset", source)
        self.assertIn("carrier:GetPivot() ~= nativeCarrierPivot", source)
        self.assertIn("model:GetPivot() ~= nativeCarrierPivot", source)
        self.assertNotIn("carrier.PivotOffset =", source)
        self.assertNotIn("carrier.CFrame:ToObjectSpace(authoredPivot)", source)
        self.assertLess(source.index("local nativeCarrierPivot"), source.index("Carrier.Prepare(carrier)"))
        self.assertLess(source.index("local nativeCarrierPivot"), source.index("SkinConnection.Connect(model, carrier"))

    def test_wrapper_pivot_is_not_a_valid_replacement_for_imported_part_pivot(self):
        # One-dimensional projection of CFrame:ToObjectSpace onto world Y.
        # A wrapper at ground level is not necessarily the skinned rig origin.
        wrapper_y, carrier_cframe_y, native_offset_y = 0.0, 3.0, 6.0
        native_pivot_y = carrier_cframe_y + native_offset_y
        wrong_rebased_offset = wrapper_y - carrier_cframe_y
        self.assertEqual(native_pivot_y, 9.0)
        self.assertEqual(carrier_cframe_y + wrong_rebased_offset, wrapper_y)
        self.assertNotEqual(native_pivot_y, carrier_cframe_y + wrong_rebased_offset)
        # Unmodified offset + PrimaryPart => original rig pivot, not ground level.
        self.assertEqual(carrier_cframe_y + native_offset_y, native_pivot_y)

    def test_both_plugins_use_the_same_loader_and_native_model_pivot(self):
        studio = json.loads((STUDIO / "plugin.project.json").read_text("utf-8"))
        landscape = json.loads((LANDSCAPE / "plugin.project.json").read_text("utf-8"))
        self.assertEqual(studio["tree"]["modules"]["DecoAssetLoader"]["$path"],
                         "modules/DecoAssetLoader.luau")
        self.assertEqual(landscape["tree"]["modules"]["DecoAssetLoader"]["$path"],
                         "../studio-plugin/modules/DecoAssetLoader.luau")
        for filename in (STUDIO / "modules/DecoPlacement.luau",
                         LANDSCAPE / "modules/LandscapeAssetPlacement.luau"):
            src = filename.read_text("utf-8")
            self.assertIn(":PivotTo(pivot)", src)
            self.assertNotIn(".PivotOffset =", src)

    def test_static_sway_uses_native_rig_pivot_without_rebasing(self):
        source = (LANDSCAPE / "modules/LandscapeSwayAuthoring.luau").read_text("utf-8")
        self.assertIn('local pivot = model:GetPivot()', source)
        self.assertNotIn('PivotOffset =', source)
        self.assertNotIn('Bone', source)

    def test_imported_bones_are_not_rebuilt_or_reparented_by_loader(self):
        src = (STUDIO / "modules/DecoAssetLoader.luau").read_text("utf-8")
        self.assertNotIn('Instance.new("Bone")', src)
        self.assertNotIn('bone.Parent =', src)
        self.assertNotIn('model:PivotTo(', src)


if __name__ == "__main__":
    unittest.main()
