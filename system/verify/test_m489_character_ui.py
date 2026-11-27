"""M489 presentation contracts and executable pure eye-state regression."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
def read(path):
    return (ROOT / path).read_text(encoding='utf8')

class CharacterUiM489(unittest.TestCase):
    def test_fullscreen_layers_do_not_move_safe_area_controls(self):
        layer = read('src/client/FullScreenLayer.luau')
        c = read('src/client/character/CharacterCreationController.luau')
        p = read('src/client/character/CharacterCreationPanel.luau')
        m = read('src/client/localization/LanguageMenuController.luau')
        self.assertIn('gui.ScreenInsets = Enum.ScreenInsets.None', layer)
        self.assertIn('gui.ClipToDeviceSafeArea = false', layer)
        self.assertIn('gui.Enabled = owner.Enabled', layer)
        self.assertIn('owner.Destroying:Connect', layer)
        self.assertIn('gui.IgnoreGuiInset = false', c)
        self.assertIn('gui.IgnoreGuiInset = false', m)
        self.assertIn('overlay.Parent = overlayParent', p)
        self.assertIn('"Game1CreationOverlay", 302', c)
        self.assertIn('"Game1CreationCurtain", gui.DisplayOrder - 1', c)
        self.assertIn('"Game1LanguageBackdrop", 300', m)

    def test_language_confirm_is_nonblocking_and_persistence_is_distinct(self):
        m = read('src/client/localization/LanguageMenuController.luau')
        s = read('src/server/localization/PlayerLanguageService.luau')
        confirm = m.split('confirm.Activated:Connect(function()')[1].split('State.Changed:Connect')[0]
        self.assertLess(confirm.index('shade.Visible = false'), confirm.index('task.spawn'))
        self.assertLess(confirm.index('State.SetLocale(chosen)'), confirm.index('shade.Visible = false'))
        self.assertNotIn('Game1SaveFailed', m)
        self.assertIn('response.persisted == false', confirm)
        self.assertEqual(s.count('{ok = true, persisted = false, locale = value}'), 2)
        self.assertIn('{ok = true, persisted = true, locale = value}', s)
        self.assertIn('error = "unsupported_locale"', s)
        self.assertLess(s.index('player:SetAttribute(ATTRIBUTE, value)', s.index('local function save')), s.index('store:SetAsync'))

    def test_flags_font_and_compact_selection(self):
        m = read('src/client/localization/LanguageMenuController.luau')
        p = read('src/client/character/CharacterCreationPanel.luau')
        c = read('src/client/character/CharacterCreationController.luau')
        a = read('src/client/character/CharacterCreationAppearanceView.luau')
        catalog = json.loads(read('assets/manifests/game-localization.json'))
        for locale in catalog['locales']:
            self.assertIn('["' + locale + '"] = "', m.split('local FLAGS')[1].split('local function corner')[0])
        self.assertIn('FLAGS[locale] .. "  " .. Catalog.locales[locale]', m)
        self.assertIn('controls.selectionCaption.Text = tostring(index)', read('src/client/character/CharacterRosterView.luau'))
        self.assertIn('"creation.selection_level", {level = level or 1}', p)
        self.assertNotIn('selectionHint', p)
        self.assertNotIn('creation.session_only', c)
        for key, expected in [('selection_title','Select character'), ('human_male','Human Male'), ('human_female','Human Female'), ('selection_level','Level {level}')]:
            row = catalog['groups']['creation']['creation.' + key]
            self.assertEqual(row['translations']['en-us'], expected)
            self.assertEqual(set(row['translations']), set(catalog['locales']))
        actor = read('src/client/combat/HealthBarView.luau')
        self.assertIn('title.Font = Enum.Font.GothamBold', actor)
        for view in (m,p,a,read('src/client/character/CharacterCreationColorPalette.luau')):
            self.assertNotRegex(view,r'Enum\.Font\.(GothamSemibold|GothamMedium|Gotham|Code)\b')
        self.assertIn('button.Text = tostring(i)', a)
        self.assertIn('layout.CellSize = UDim2.fromOffset(46, 46)', a)
        self.assertIn('activeTab = firstCategory("human_male")', c)
        self.assertIn('activeTab = firstCategory("human_female")', c)
        self.assertIn('ipairs(Panel.Categories)', c)

    def test_eye_state_has_single_preview_commit_solver_and_snapshot(self):
        e = read('src/client/character/CharacterCreationEyeEdit.luau')
        c = read('src/client/character/CharacterCreationController.luau')
        self.assertIn('state.previous = table.clone(pair)', e)
        self.assertIn('return table.clone(state.previous or pair)', e)
        self.assertIn('if locked then return {l = value, r = value} end', e)
        self.assertEqual(c.count('EyeEdit.Paint('), 2)
        self.assertIn('EyeEdit.Toggle(eyeLocks[selected], values.colors.eyes, side)', c)
        self.assertIn('eyeLocks[id] = EyeEdit.New(choice.colors.eyes)', c)

    def test_eye_state_behavior_luau(self):
        cli = shutil.which('luau')
        if not cli:
            self.skipTest('Luau CLI unavailable')
        subprocess.run([cli, 'system/verify/character_eye_edit_m489.luau'], cwd=ROOT, check=True, timeout=20)

if __name__ == '__main__':
    unittest.main()
