"""M119: Plots preview is an isolated, reversible Studio authoring utility."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "system/studio-plugin"
MAIN = (PLUGIN / "Game1Bridge.server.luau").read_text(encoding="utf-8")
CATALOG = (PLUGIN / "modules/StudioPlotsCatalog.luau").read_text(encoding="utf-8")
PREVIEW = (PLUGIN / "modules/StudioPlotsVisibility.luau").read_text(encoding="utf-8")
INSTALL = (PLUGIN / "install.ps1").read_text(encoding="utf-8")
PROJECT = json.loads((PLUGIN / "plugin.project.json").read_text(encoding="utf-8"))


class StudioPlotsPreviewM119(unittest.TestCase):
    def test_manifest_and_composition_only_add_plots_modules(self):
        for module in ("StudioPlotsCatalog", "StudioPlotsVisibility"):
            self.assertEqual(PROJECT["tree"]["modules"][module]["$path"], f"modules/{module}.luau")
            self.assertIn(f"'{module}'", INSTALL)
        self.assertIn('require(script.Parent.modules.StudioPlotsVisibility)', MAIN)
        self.assertIn('StudioPlotsVisibility.new({', MAIN)
        self.assertIn('CoreGui = game:GetService("CoreGui")', MAIN)
        self.assertIn('TweenService = game:GetService("TweenService")', MAIN)
        self.assertIn("'Game1PlotsPreview'", INSTALL)
        self.assertIn('"Game1Plots"', PREVIEW)
        self.assertIn('"Plots"', PREVIEW)

    def test_state_machine_has_three_stages_and_no_persistent_plugin_setting(self):
        self.assertIn('local nextState = (self.state + 1) % 3', PREVIEW)
        self.assertIn('"hidden", "volumes", "volumes + numbers"', PREVIEW)
        self.assertIn('if self.state == 2 then numberOriginal.localTransparency else 1', PREVIEW)
        self.assertIn('if self.state == 0 then 1 else VOLUME_ALPHA', PREVIEW)
        self.assertNotIn('SetSetting(', PREVIEW)
        self.assertNotIn('GetSetting(', PREVIEW)

    def test_catalog_only_selects_exact_plot_and_number_objects(self):
        self.assertIn('workspace:FindFirstChild("Plots")', CATALOG)
        self.assertIn('string.format("%02d", index)', CATALOG)
        self.assertIn('"plot_" .. folderName .. "_volume"', CATALOG)
        self.assertIn('"plot_" .. tostring(index) .. "_volume"', CATALOG)
        self.assertIn('volume:FindFirstChild(tostring(index))', CATALOG)
        self.assertIn('numbersRoot:FindFirstChild(tostring(index))', CATALOG)
        self.assertIn('if instance:IsA("BasePart") then', CATALOG)
        self.assertIn('for index = 1, 50 do', CATALOG)
        for forbidden in ('Instance.new("Folder")', ':Clone()', ':PivotTo(', 'CFrame =', 'WeldConstraint'):
            self.assertNotIn(forbidden, CATALOG)

    def test_preview_visuals_are_coregui_only_in_edit(self):
        self.assertIn('Instance.new("BoxHandleAdornment")', PREVIEW)
        self.assertIn('adornment.Parent = self.coreGui', PREVIEW)
        self.assertIn('adornment.Adornee = volume', PREVIEW)
        self.assertIn('adornment.Size = volume.Size', PREVIEW)
        self.assertIn('volume:GetPropertyChangedSignal("Size")', PREVIEW)
        self.assertIn('self.tweenService:Create(instance, FADE', PREVIEW)
        self.assertIn('self:_cancel(instance)', PREVIEW)
        self.assertNotIn('part.Transparency =', PREVIEW)
        self.assertNotIn('volume.Transparency =', PREVIEW)
        for forbidden in ('Instance.new("Part")', ':Clone()', ':PivotTo(', '.CFrame =', '.Anchored =', '.CanCollide =', '.Parent = volume'):
            self.assertNotIn(forbidden, PREVIEW)

    def test_number_visibility_is_reversible_and_edit_mode_only(self):
        self.assertIn('local saved = StudioPlotsPartPolicy.Capture(part)', PREVIEW)
        self.assertIn('self.originalProperties[part] = saved', PREVIEW)
        self.assertIn('volume.LocalTransparencyModifier = 1', PREVIEW)
        self.assertIn('if fresh then numberPart.LocalTransparencyModifier = 1 end', PREVIEW)
        self.assertIn('StudioPlotsPartPolicy.Restore(part, original)', PREVIEW)
        self.assertIn('config.plugin.Unloading:Connect', PREVIEW)
        self.assertIn('GetPropertyChangedSignal("RunState")', PREVIEW)
        self.assertIn('if self.phase ~= "edit" then', PREVIEW)
        self.assertIn('self:_release()', PREVIEW)
        self.assertIn('tween:Cancel()', PREVIEW)
        self.assertIn('overlay:Destroy()', PREVIEW)
        self.assertIn('connection:Disconnect()', PREVIEW)
        self.assertIn('if self.destroyed then return end', PREVIEW)

    def test_missing_plot_folder_fails_without_editing_state(self):
        self.assertIn('if not plots or not plots:IsA("Folder") then', CATALOG)
        self.assertIn('return {}, 50, 50', CATALOG)
        self.assertIn('warn("[game1][plots] Workspace.Plots folder not found")', PREVIEW)
        self.assertIn('if volumes == 0 then', PREVIEW)
        self.assertIn('self.state = 0', PREVIEW)


if __name__ == "__main__":
    unittest.main()
