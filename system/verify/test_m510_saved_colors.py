"""M510 account palette wiring (Studio smoke validates Luau data and UI)."""
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[2]

def read(path):
    return (ROOT / path).read_text(encoding='utf8')

class SavedColors(unittest.TestCase):
    def test_account_store_is_independent_and_server_authoritative(self):
        store = read('src/server/character/CharacterCreationSavedColorStore.luau')
        self.assertIn('GetDataStore("game1_account_colors_v1")', store)
        self.assertIn('tostring(player.UserId)', store)
        self.assertIn('database:UpdateAsync(key(player)', store)
        self.assertIn('Colors.Add(if previous then previous.colors else nil, value)', store)
        self.assertIn('if action == "save" and not color', store)
        self.assertIn('RunService:IsStudio()', store)
        self.assertIn('previous.schemaVersion ~= 1', store)
        self.assertIn('busy[player]', store)
        gateway = read('src/server/character/CharacterCreationGateway.luau')
        self.assertIn('SavedColors.Bind(remotes)', gateway)
        self.assertIn('SavedColors.Forget(player)', gateway)

    def test_shared_palette_all_channels_and_two_views(self):
        controller = read('src/client/character/CharacterCreationController.luau')
        self.assertIn('local savedColors: {string} = {}', controller)
        self.assertIn('paletteRequest("read", nil)', controller)
        self.assertIn('palette:SetSavedColors(savedColors)', controller)
        self.assertIn('end, savedColors)', controller)
        self.assertIn('paletteRequest("save", hex)', controller)
        view = read('src/client/character/CharacterCreationAppearanceView.luau')
        self.assertIn('SavedRow.Render(saved, savedColors, current, pick)', view)
        self.assertIn('onCustomColor("hair", channel, current, title)', view)
        self.assertIn('Language.Translate("creation.eyebrows_color")) end, nil, nil, savedColors)', view)
        self.assertIn('toggleEyeColorsLocked(side) end else nil, savedColors)', view)
        palette = read('src/client/character/CharacterCreationColorPalette.luau')
        self.assertIn('self.title.Text = titleText', palette)
        self.assertIn('save.Text = "💾"', palette)
        self.assertIn('SavedRow.Render(saved, savedColors', palette)
        self.assertIn('setHex(value, true)', palette)
        save = palette.split('save.Activated:Connect(function()')[1].split('local function coordinate')[0]
        self.assertNotIn('onCommit(', save)
        self.assertNotIn('overlay.Visible = false', save)

    def test_validation_limit_and_mobile_scrolling(self):
        shared = read('src/shared/character/CharacterCreationSavedColors.luau')
        self.assertIn('Colors.Limit = 24', shared)
        self.assertIn('^#%x%x%x%x%x%x$', shared)
        self.assertIn('not table.find(result, color)', shared)
        self.assertIn('table.insert(result, 1, color)', shared)
        row = read('src/client/character/CharacterCreationSavedColorRow.luau')
        self.assertIn('Enum.ScrollingDirection.X', row)
        self.assertIn('swatch.Activated:Connect', row)

if __name__ == '__main__': unittest.main()
