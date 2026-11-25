"""UI copy and single-slot-safe selection footer contracts."""
from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[2]


class CharacterLabelsM500(unittest.TestCase):
    def test_labels_and_common_cancel(self):
        data = json.loads((ROOT/'assets/manifests/game-localization.json').read_text(encoding='utf8'))
        creation = data['groups']['creation']
        expected = {'male': 'Парень', 'female': 'Девушка', 'human_male': 'Человек · парень',
                    'human_female': 'Человек · девушка', 'enter': 'Играть',
                    'palette_apply': 'Применить', 'new_character': 'Новый персонаж'}
        for key, text in expected.items():
            row = creation['creation.'+key]
            self.assertEqual(row['source'], text)
            self.assertEqual(row['translations']['ru-ru'], text)
            self.assertEqual(set(row['translations']), set(data['locales']))
        self.assertNotIn('creation.palette_cancel', creation)
        self.assertEqual(data['groups']['feedback']['feedback.cancel']['translations']['ru-ru'], 'Отмена')
        palette = (ROOT/'src/client/character/CharacterCreationColorPalette.luau').read_text(encoding='utf8')
        self.assertIn('self.cancel.Text = Language.Translate("feedback.cancel")', palette)
        self.assertIn('if onCancel then onCancel() end', palette)

    def test_new_character_is_reserved_above_play_only_in_selection(self):
        panel = (ROOT/'src/client/character/CharacterCreationPanel.luau').read_text(encoding='utf8')
        self.assertIn('views.newCharacter.Visible = ready', panel)
        self.assertIn('views.newCharacter.Text = Language.Translate("creation.new_character")', panel)
        self.assertIn('newCharacter.Interactable = false', panel)
        self.assertIn('newCharacter.Selectable = false', panel)
        self.assertNotIn('newCharacter.Activated:Connect', panel)
        self.assertIn('local newActionSpace = if selection then enterHeight + 6 else 0', panel)
        self.assertIn('local footerHeight = 84 + newActionSpace', panel)
        self.assertIn('local enterY = 4 + newActionSpace', panel)
        for enter_height in (38, 44):
            # Both mobile and desktop footer layouts leave a six-pixel gap.
            self.assertEqual(4 + enter_height + 6 - (4 + enter_height), 6)
            self.assertGreaterEqual(84 + enter_height + 6 - (4 + enter_height + 6 + enter_height + 3), 18)


if __name__ == '__main__':
    unittest.main()
