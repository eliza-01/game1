"""M120: reversible plot picking and playtest state contracts."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "system/studio-plugin"
POLICY = (PLUGIN / "modules/StudioPlotsPartPolicy.luau").read_text(encoding="utf-8")
PREVIEW = (PLUGIN / "modules/StudioPlotsVisibility.luau").read_text(encoding="utf-8")
MAIN = (PLUGIN / "Game1Bridge.server.luau").read_text(encoding="utf-8")
MANIFEST = json.loads((PLUGIN / "plugin.project.json").read_text(encoding="utf-8"))
INSTALL = (PLUGIN / "install.ps1").read_text(encoding="utf-8")


class PlotsPlaytestM120(unittest.TestCase):
    def test_selection_service_and_new_policy_composed(self):
        self.assertIn('Selection = Selection,', MAIN)
        self.assertIn('local StudioPlotsPartPolicy = require(script.Parent.StudioPlotsPartPolicy)', PREVIEW)
        self.assertIn("'StudioPlotsPartPolicy'", INSTALL)
        self.assertEqual(MANIFEST['tree']['modules']['StudioPlotsPartPolicy']['$path'],
                         'modules/StudioPlotsPartPolicy.luau')

    def test_edit_viewport_filter_is_separate_from_play_physics(self):
        self.assertIn('function Policy.Edit(part: BasePart, saved: any, _accessible: boolean)', POLICY)
        self.assertIn('applyInteraction(part, saved, true, false)', POLICY)
        self.assertIn('self:_removeHiddenSelection()', PREVIEW)
        self.assertIn('StudioPlotsPartPolicy.Edit(volume, volumeOriginal, self.state ~= 0)', PREVIEW)
        self.assertIn('StudioPlotsPartPolicy.Edit(numberPart, numberOriginal, self.state == 2)', PREVIEW)
        self.assertIn('self.selectionFilter:Hide(volume, volumeOriginal.collisionGroup)', PREVIEW)
        self.assertIn('self.selectionFilter:Hide(numberPart, numberOriginal.collisionGroup)', PREVIEW)

    def test_playtest_inherits_state_and_anchors_volumes(self):
        self.assertIn('local playtest = self.phase == "play"', PREVIEW)
        self.assertIn('self.state ~= 0, true, VOLUME_COLOR, VOLUME_ALPHA', PREVIEW)
        self.assertIn('self.state == 2, false, VOLUME_COLOR, VOLUME_ALPHA', PREVIEW)
        self.assertIn('part.Anchored = true', POLICY)
        self.assertIn('part.Transparency = alpha', POLICY)
        self.assertIn('part.Transparency = 1', POLICY)
        self.assertIn('part.LocalTransparencyModifier = 1', POLICY)
        self.assertNotIn('self.state = 0\n        self.button:SetActive(false)\n        if not', PREVIEW)

    def test_pause_does_not_reset_or_reinitialize(self):
        self.assertIn('if runState == Enum.RunState.Paused then return end', PREVIEW)
        self.assertIn('if self.phase ~= "edit" then', PREVIEW)
        self.assertIn('task.defer(function()', PREVIEW)
        self.assertNotIn('self.state = 0\n        self.button:SetActive(false)\n        if not self.runService:IsRunning()', PREVIEW)

    def test_original_authoring_properties_all_restored(self):
        for property_name in ('localTransparency','transparency','color','anchored','locked',
                              'canCollide','canQuery','canTouch','castShadow'):
            self.assertIn(property_name + ' = part.', POLICY)
        for field in ('LocalTransparencyModifier','Transparency','Color','Anchored',
                      'CastShadow'):
            self.assertIn('part.' + field + ' = saved.', POLICY)
        self.assertIn('applyInteraction(part, saved, true, false)', POLICY)
        self.assertIn('self:_release()', PREVIEW)
        self.assertIn('config.plugin.Unloading:Connect', PREVIEW)
        self.assertIn('self.tweens[instance] = nil', PREVIEW)

    def test_never_modify_identity_rigs_or_scene(self):
        combined = POLICY + PREVIEW
        for banned in ('PivotTo(', 'Instance.new("Part")', 'Destroy()\n        part.',
                       'part.Parent =', 'volume.Parent =', 'WeldConstraint',
                       'CanCollide = true', 'SetAttribute(', 'SetSetting('):
            self.assertNotIn(banned, combined)


if __name__ == '__main__':
    unittest.main()
