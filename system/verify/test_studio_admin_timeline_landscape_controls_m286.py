"""M286 interaction and ownership regressions.

Actual Roblox plugin input and ViewportFrame skinned rendering still require Studio.
"""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
LAND = ROOT / 'system' / 'landscape-plugin'
STUDIO = ROOT / 'system' / 'studio-plugin' / 'modules'


def read(path):
    return path.read_text(encoding='utf-8')


class LandscapeControls(unittest.TestCase):
    def test_both_tools_use_same_drag_and_color_components(self):
        project = json.loads(read(LAND / 'plugin.project.json'))
        self.assertEqual(project['tree']['modules']['LandscapeAdjustments']['$path'], 'modules/LandscapeAdjustments.luau')
        for name in ('LandscapeWidget', 'LandscapeAssetsWidget'):
            source = read(LAND / 'modules' / f'{name}.luau')
            self.assertIn('require(script.Parent.LandscapeAdjustments)', source)
            self.assertIn('Adjustments.Slider(', source)
            self.assertIn('Adjustments.Color(', source)
        controls = read(LAND / 'modules/LandscapeAdjustments.luau')
        for word in ('UserInputService.InputChanged', 'UserInputService.InputEnded',
                     'InputBegan:Connect', 'input.UserInputType == Enum.UserInputType.Touch',
                     'math.log(number / minimum)', 'Color3.fromHSV', 'ColorSequence.new',
                     'hexExact.FocusLost', 'valueButton.MouseButton1Click'):
            self.assertIn(word, controls)
        self.assertNotIn('InputChanged:Connect(function() options.changed', controls)

    def test_dragging_does_not_write_db_or_place_and_is_throttled(self):
        controls = read(LAND / 'modules/LandscapeAdjustments.luau')
        self.assertNotIn('GetService("Workspace")', controls)
        self.assertNotIn('ChangeHistoryService', controls)
        self.assertNotIn('SetSetting(', controls)
        main = read(LAND / 'LandscapePainter.server.luau')
        self.assertIn('branchSaveScheduled', main)
        self.assertIn('task.delay(0.35', main)
        self.assertIn('branch:SetSettings(diameter, level, color)', main)
        placement = read(LAND / 'modules/LandscapeAssetPlacement.luau')
        self.assertIn('pendingConfigPreview', placement)
        self.assertIn('1 / MAX_PREVIEW_HZ', placement)
        self.assertIn('self:UpdateCursor(true)', placement)

    def test_profile_use_and_apply_remain_distinct(self):
        source = read(LAND / 'modules/LandscapeAssetsWidget.luau')
        self.assertIn('self.actions.configChanged(table.clone(self.config))', source)
        self.assertIn('actions.useProfile(self.selectedProfile', source)
        self.assertIn('actions.applyProfile(self.selectedProfile)', source)
        self.assertIn('новые размещения используют сохранённый профиль', source)
        self.assertIn('SelectProfile(id)', source)
        self.assertIn('Сохранить новый профиль', source)
        self.assertIn('name = "Yaw · по нормали"', source)


class TimelineAdminPreview(unittest.TestCase):
    def test_uses_existing_stand_builder_not_a_new_character_assembly(self):
        builder = read(STUDIO / 'StudioCharacterStandBuilder.luau')
        self.assertIn('function Builder.AdminProfile(expectedCharacterId:', builder)
        self.assertIn('registry.studioAdminArchetypeId', builder)
        self.assertIn('profile.mode == "assembly"', builder)
        self.assertIn('assemblyBuilder.Build(row.assembly', builder)
        preview = read(STUDIO / 'StudioTimelinePreview.luau')
        self.assertIn('require(script.Parent.StudioCharacterStandBuilder)', preview)
        self.assertIn('StudioCharacterStandBuilder.AdminProfile(characterId)', preview)
        self.assertIn('StudioCharacterStandBuilder.Build(AssetService, profile)', preview)
        self.assertIn('visible == 0', preview)
        self.assertIn('preview.Parent = timelineWorld', preview)
        self.assertNotIn('preview.Parent = Workspace', preview)

    def test_only_characters_use_admin_and_monsters_keep_published_model(self):
        command = read(STUDIO / 'StudioTimelineEditorCommands.luau')
        self.assertIn('tostring(data.subjectType or "") == "characters"', command)
        self.assertIn('preview = loadTimelineAdminModel(tostring(data.subjectId or ""))', command)
        self.assertIn('preview = loadTimelinePreviewModel(modelAssetId)', command)
        self.assertLess(command.index('local sequence = loadTimelineSequence(animationAssetId)'),
                        command.index('preview = loadTimelineAdminModel('))
        self.assertIn('poseSampler.Build(preview, sequence)', command)
        self.assertIn('action = "set-event"', command)
        self.assertIn('action = "ready"', command)

    def test_hair_uses_existing_runtime_follower_per_scrub(self):
        client = read(ROOT / 'src/client/character/BoneMountedAttachmentController.luau')
        self.assertIn('BoneMountedAttachmentController.UpdateCharacter = updateCharacter', client)
        command = read(STUDIO / 'StudioTimelineEditorCommands.luau')
        self.assertIn('previewService.RefreshAccessories(timelineEditor.preview)', command)
        preview = read(STUDIO / 'StudioTimelinePreview.luau')
        self.assertIn('BoneMountedAttachmentController', preview)
        self.assertIn('hairFollower.UpdateCharacter(preview)', preview)
        self.assertNotIn('RenderStepped:Connect', preview)


if __name__ == '__main__':
    unittest.main()
