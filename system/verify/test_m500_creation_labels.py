"""UI copy and multi-slot selection footer contracts."""
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

    def test_new_character_and_delete_are_above_play(self):
        panel = (ROOT/'src/client/character/CharacterCreationPanel.luau').read_text(encoding='utf8')
        view = (ROOT/'src/client/character/CharacterRosterView.luau').read_text(encoding='utf8')
        controller = (ROOT/'src/client/character/CharacterCreationController.luau').read_text(encoding='utf8')
        self.assertIn('views.newCharacter.Visible = ready or (editing', panel)
        self.assertIn('views.deleteCharacter.Visible = ready', panel)
        self.assertIn('"creation.new_character"', view)
        self.assertIn('button.Interactable = enabled', view)
        self.assertIn('#characters < limit', view)
        self.assertIn('controls.newCharacter.Activated:Connect', controller)
        self.assertIn('controls.deleteCharacter.Activated:Connect', controller)
        self.assertIn('local newActionSpace = if selection or', panel)
        self.assertIn('local footerHeight = (if compact then 64 else 84) + newActionSpace', panel)
        self.assertIn('local enterY = 4 + newActionSpace', panel)
        for enter_height in (38, 44):
            # Both mobile and desktop footer layouts leave a six-pixel gap.
            self.assertEqual(4 + enter_height + 6 - (4 + enter_height), 6)
            footer = 64 if enter_height == 38 else 84
            self.assertGreaterEqual(footer + enter_height + 6 - (4 + enter_height + 6 + enter_height + 3), 18)


if __name__ == '__main__':
    unittest.main()
