"""M121 StudioSelectable picking policy and lifecycle regression guards."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / 'system/studio-plugin'
FILTER = (PLUGIN / 'modules/StudioPlotsSelectionFilter.luau').read_text(encoding='utf-8')
POLICY = (PLUGIN / 'modules/StudioPlotsPartPolicy.luau').read_text(encoding='utf-8')
PREVIEW = (PLUGIN / 'modules/StudioPlotsVisibility.luau').read_text(encoding='utf-8')
MAIN = (PLUGIN / 'Game1Bridge.server.luau').read_text(encoding='utf-8')
MANIFEST = json.loads((PLUGIN / 'plugin.project.json').read_text(encoding='utf-8'))
INSTALL = (PLUGIN / 'install.ps1').read_text(encoding='utf-8')


class PlotsSelectionFilterM121(unittest.TestCase):
    def test_new_adapter_is_composed_and_shipped(self):
        self.assertIn('StudioPlotsSelectionFilter = require(', PREVIEW)
        self.assertIn('selectionFilter = StudioPlotsSelectionFilter.new(config.PhysicsService)', PREVIEW)
        self.assertIn('PhysicsService = game:GetService("PhysicsService")', MAIN)
        self.assertEqual(MANIFEST['tree']['modules']['StudioPlotsSelectionFilter']['$path'],
                         'modules/StudioPlotsSelectionFilter.luau')
        self.assertIn("'StudioPlotsSelectionFilter'", INSTALL)

    def test_editor_picker_uses_roblox_supported_collision_group(self):
        self.assertIn('local STUDIO_GROUP = "StudioSelectable"', FILTER)
        self.assertIn('local HIDDEN_GROUP = "Game1PlotsPreviewHidden"', FILTER)
        self.assertIn('CollisionGroupsAreCollidable(STUDIO_GROUP, HIDDEN_GROUP)', FILTER)
        self.assertIn('CollisionGroupSetCollidable(STUDIO_GROUP, HIDDEN_GROUP, false)', FILTER)
        self.assertIn('part.CollisionGroup = HIDDEN_GROUP', FILTER)
        self.assertIn('part.CollisionGroup = restoreTo', FILTER)
        # Regression: Locked/CanQuery alone do not let you pick through volumes.
        edit = POLICY.split('function Policy.Edit(')[1].split('function Policy.Play(')[0]
        self.assertIn('applyInteraction(part, saved, true, false)', edit)
        self.assertNotIn('applyInteraction(part, saved, accessible, false)', edit)

    def test_only_hidden_volumes_and_numbers_receive_selection_group(self):
        self.assertIn('if self.state == 0 then', PREVIEW)
        self.assertIn('self.selectionFilter:Hide(volume, volumeOriginal.collisionGroup)', PREVIEW)
        self.assertIn('self.selectionFilter:Restore(volume, volumeOriginal.collisionGroup)', PREVIEW)
        self.assertIn('if self.state == 2 then', PREVIEW)
        self.assertIn('self.selectionFilter:Hide(numberPart, numberOriginal.collisionGroup)', PREVIEW)
        self.assertIn('self.selectionFilter:Restore(numberPart, numberOriginal.collisionGroup)', PREVIEW)

    def test_saved_group_restored_before_play_after_stop_and_unload(self):
        self.assertIn('self.selectionFilter:Restore(volume, volumeOriginal.collisionGroup)', PREVIEW)
        self.assertIn('self.selectionFilter:Restore(numberPart, numberOriginal.collisionGroup)', PREVIEW)
        self.assertIn('for part, original in pairs(self.originalProperties) do', PREVIEW)
        self.assertIn('self.selectionFilter:Restore(part, original.collisionGroup)', PREVIEW)
        self.assertIn('StudioPlotsPartPolicy.Restore(part, original)', PREVIEW)
        self.assertIn('GetPropertyChangedSignal("RunState")', PREVIEW)
        self.assertIn('config.plugin.Unloading:Connect', PREVIEW)

    def test_crash_recovery_and_no_unrelated_asset_mutation(self):
        self.assertIn('local ORIGINAL_GROUP_ATTRIBUTE = "__Game1PlotsOriginalCollisionGroup"', FILTER)
        self.assertIn('part:GetAttribute(ORIGINAL_GROUP_ATTRIBUTE)', FILTER)
        self.assertIn('part:SetAttribute(ORIGINAL_GROUP_ATTRIBUTE, originalGroup)', FILTER)
        self.assertIn('part:SetAttribute(ORIGINAL_GROUP_ATTRIBUTE, nil)', FILTER)
        self.assertIn('saved.collisionGroup = StudioPlotsSelectionFilter.OriginalGroup(part)', PREVIEW)
        for forbidden in ('part.CFrame =', 'part.Size =', 'part.Parent =', 'part:Destroy()',
                          'part:PivotTo(', 'WeldConstraint', 'ServerStorage', 'ReplicatedStorage'):
            self.assertNotIn(forbidden, FILTER)
        self.assertNotIn('Filter:Hide(', POLICY)


if __name__ == '__main__':
    unittest.main()
