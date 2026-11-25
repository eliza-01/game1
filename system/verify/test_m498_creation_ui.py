"""M498 UI-only category and palette contracts; rendered drag tested in Studio."""
from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[2]


def source(path):
    return (ROOT / path).read_text(encoding='utf8')


class CreationUiM498(unittest.TestCase):
    def test_only_three_categories_with_short_russian_names(self):
        panel = source('src/client/character/CharacterCreationPanel.luau')
        controller = source('src/client/character/CharacterCreationController.luau')
        self.assertIn('local TABS = table.freeze({"hair", "eyebrows", "eyes"})', panel)
        self.assertIn('ipairs(Panel.Categories)', controller)
        self.assertIn('visible[category] = #entries > 0', controller)
        phrases = json.loads(source('assets/manifests/game-localization.json'))['groups']['creation']
        for key, label in [('hair', 'Причёска'), ('eyebrows', 'Брови'), ('eyes', 'Глаза')]:
            row = phrases['creation.' + key]
            self.assertEqual(row['source'], label)
            self.assertEqual(row['translations']['ru-ru'], label)
        # Appearance recipes still have a head and four independent materials.
        self.assertIn('head = "head"', source('src/shared/character/CharacterCreationMaterials.luau'))

    def test_primary_label_only_and_extras_keep_channel(self):
        view = source('src/client/character/CharacterCreationAppearanceView.luau')
        self.assertIn('local title = Language.Translate("creation.hair_color")', view)
        self.assertIn('if channel ~= "primary" then title ..= " · " .. channel end', view)
        self.assertIn('function(hex) onColor("hair", hex, channel) end', view)
        self.assertIn('function() onCustomColor("hair", channel, current, title) end', view)

    def test_brightness_handle_follows_same_value_for_all_inputs(self):
        palette = source('src/client/character/CharacterCreationColorPalette.luau')
        self.assertIn('valueCursor.Parent = valueBar', palette)
        self.assertIn('valueCursor.Position = UDim2.fromScale(v, 0.5)', palette)
        display = palette[palette.index('local function display('):palette.index('local function setHex(')]
        self.assertIn('valueCursor.Position', display)
        self.assertIn('if emit and onPreview then onPreview(chosen) end', display)
        self.assertIn('h, s, v = parsed:ToHSV()\n        display(emit)', palette)
        self.assertIn('v = x\n        end\n        display(true)', palette)
        self.assertIn('attach(valueHit, "brightness")', palette)
        self.assertIn('valueHit.ZIndex = 37', palette)
        self.assertIn('valueCursor.ZIndex = 36', palette)


if __name__ == '__main__':
    unittest.main()
