"""m484: separate creation/selection/world ownership and live palette UI."""
from __future__ import annotations
import json
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]

def source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')

class CharacterLifecycleM484(unittest.TestCase):
    def test_no_character_autoload_even_during_service_boot(self):
        bootstrap = source('src/server/init.server.luau')
        self.assertLess(bootstrap.index('CharacterAutoLoads = false'),
                        bootstrap.index('authoringCleanup.Start()'))
        gateway = source('src/server/character/CharacterCreationGateway.luau')
        join = gateway.split('function Gateway:Join(player: Player)')[1].split('function Gateway:Leave')[0]
        self.assertIn('self:Stage(player, "loading")', join)
        self.assertIn('self:Stage(player, "selection")', join)
        self.assertIn('self:Stage(player, "creation")', join)
        self.assertIn('"storage_unavailable"', join)
        self.assertNotIn('task.defer(self.spawn, player, "")', join)
        # Explicit disabled-mode test loadout is retained, not implicit gameplay spawn.
        self.assertIn('if not self.enabled then', join)

    def test_create_never_spawns_and_enter_requires_saved_authoritative_profile(self):
        gateway = source('src/server/character/CharacterCreationGateway.luau')
        create = gateway.split('create.OnServerInvoke = function')[1].split('read.OnServerInvoke = function')[0]
        self.assertNotIn('self.spawn(', create)
        self.assertIn('self.profiles.Create(player, archetypeId, checked)', create)
        self.assertIn('self:Stage(player, "selection")', create)
        enter = gateway.split('enter.OnServerInvoke = function')[1].split('switch.OnServerInvoke = function')[0]
        self.assertIn('self.profiles.Get(player)', enter)
        self.assertIn('self.validate(record.archetype, record.appearance, true)', enter)
        self.assertIn('self.profiles.SpawnFrame(player)', enter)
        self.assertIn('self.spawn(player, record.archetype, checked', enter)
        self.assertIn('self.pending[player] = nil', enter)
        self.assertIn('CharacterCreationStatus", "world"', enter)
        self.assertIn('self.profiles.RememberPosition(player, character)', gateway)
        self.assertIn('cannot_switch_while_fighting', gateway)
        self.assertIn('position_save_failed', gateway)

    def test_data_store_does_not_overwrite_when_unavailable(self):
        profile = source('src/server/character/CharacterCreationProfileStore.luau')
        self.assertIn('DataStoreService:GetDataStore', profile)
        self.assertIn('database:GetAsync', profile)
        self.assertIn('database:UpdateAsync', profile)
        self.assertIn('if not Roster.Matches(previous, session.expected) then return nil end', profile)
        self.assertIn('if not RunService:IsStudio() then return false end', profile)
        self.assertIn('sessions[player] = nil', profile)
        self.assertIn('raw.schemaVersion == 1', source('src/server/character/CharacterProfileRoster.luau'))
        self.assertIn('decodeFrame', profile)
        self.assertIn('safeFrame(root.CFrame)', profile)
        service = source('src/server/character/CharacterService.luau')
        self.assertIn('spawnOverride or CharacterRigService.SpawnCFrame(player)', service)
        self.assertIn('CharacterCreationProfileStore.RememberPosition', service)
        self.assertIn('CharacterCreationProfileStore.ForgetSession', service)
        self.assertIn('player:GetAttribute("CharacterCreationStatus") ~= "world"', service)

    def test_client_two_distinct_screens_and_saved_preview(self):
        controller = source('src/client/character/CharacterCreationController.luau')
        panel = source('src/client/character/CharacterCreationPanel.luau')
        self.assertIn('CharacterCreationRead', controller)
        self.assertIn('CharacterCreationEnter', controller)
        self.assertIn('CharacterCreationStatus', controller)
        self.assertIn('currentPreview:KeepOnly(selected)', controller)
        self.assertIn('ShowCharacterSelectionView', controller)
        self.assertIn('Panel.SetMode(controls, stage)', controller)
        self.assertIn('CharacterSelectionCard', panel)
        self.assertIn('views.content.Visible = editing', panel)
        self.assertIn('views.selectionCard.Visible = ready', panel)
        preview = source('src/client/character/CharacterCreationPreviewController.luau')
        self.assertIn('CharacterSelectionPreviewPoint', preview)
        self.assertIn('function Controller:KeepOnly', preview)
        camera = source('src/client/character/CameraController.luau')
        self.assertIn('CharacterSelectionCamera', camera)
        self.assertIn('SelectionOverview', camera)

    def test_hsv_canvas_live_preview_apply_commit_cancel_restore(self):
        palette = source('src/client/character/CharacterCreationColorPalette.luau')
        controller = source('src/client/character/CharacterCreationController.luau')
        for item in ('HSVCanvas', 'UIGradient', 'SaturationOverlay', 'BrightnessOverlay',
                     'ColorCanvasInput', 'BrightnessInput', 'InputChanged', 'Color3.fromHSV',
                     'if emit and onPreview then onPreview(chosen) end'):
            self.assertIn(item, palette)
        self.assertIn('if onCommit then onCommit(', palette)
        self.assertIn('if onCancel then onCancel()', palette)
        self.assertIn('currentPreview:Colors(id, temporary)', controller)
        self.assertIn('currentPreview:Colors(id, choices[id].colors)', controller)
        self.assertIn('paint(group, hex, channel)', controller)
        self.assertNotIn('Hue" .. tostring(col)', palette)

    def test_settings_gear_four_sections_and_own_server_switch(self):
        menu = source('src/client/localization/LanguageMenuController.luau')
        for name in ('Settings_language', 'CharacterCreationManage',
                     'settings.change_character', 'settings.coming_soon'):
            self.assertIn(name if name != 'Settings_language' else '"Settings_" .. tab', menu)
        self.assertIn('LauncherView.Decorate(launcher)', menu)
        self.assertNotIn('"🌐  "', menu)
        manifest = json.loads(source('assets/manifests/game-localization.json'))
        for category, keys in {
            'creation': ('creation.create', 'creation.selection_title', 'creation.session_only'),
            'settings': ('settings.language', 'settings.character', 'settings.graphics',
                         'settings.sound', 'settings.change_character')}.items():
            for key in keys:
                self.assertEqual(set(manifest['groups'][category][key]['translations']),set(manifest['locales']))

if __name__ == '__main__': unittest.main()
