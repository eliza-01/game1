"""M482: creation visual controls, rig mount reuse, terrain focus and options persistence."""
from __future__ import annotations
import json
import sys
import tempfile
import unittest
from pathlib import Path
from copy import deepcopy

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'system/control-center'))
from services.character_creation_settings import DEFAULTS, normalize_character_creation
from migrations.m482_creation_appearance_controls import migrate


class CharacterCreationM482(unittest.TestCase):
    def test_exactly_three_editable_colors_for_each_channel(self):
        self.assertEqual(set(DEFAULTS['colorPresets']), {'hair','eyes','eyebrows'})
        for channel in DEFAULTS['colorPresets']:
            self.assertEqual(len(DEFAULTS['colorPresets'][channel]), 3)
        invalid = deepcopy(DEFAULTS)
        invalid['colorPresets']['eyes'] = ['#000000', '#FFFFFF']
        with self.assertRaisesRegex(ValueError, 'three hex colors'):
            normalize_character_creation(invalid)
        invalid = deepcopy(DEFAULTS)
        invalid['colorPresets']['hair'][0] = 'not-a-color'
        with self.assertRaisesRegex(ValueError, 'three hex colors'):
            normalize_character_creation(invalid)
        custom = normalize_character_creation({'colorPresets': {
            'hair':['#ffffff','#000000','#e2bd83'],
            'eyes':['#112233','#445566','#778899'],
            'eyebrows':['#010203','#040506','#070809'],
        }})
        self.assertEqual(custom['colorPresets']['hair'][0], '#FFFFFF')

    def test_materials_whitelisted_and_include_plastic(self):
        self.assertIn('Plastic', DEFAULTS['materialChoices']['eyes'])
        self.assertIn('Plastic', DEFAULTS['materialChoices']['hair'])
        for disallowed in ('FakeMaterial', 'NotAMaterial'):
            invalid = deepcopy(DEFAULTS)
            invalid['materialChoices']['hair'] = ['Plastic', disallowed]
            with self.assertRaisesRegex(ValueError, 'valid unique Roblox materials'):
                normalize_character_creation(invalid)
        invalid = deepcopy(DEFAULTS)
        invalid['materialChoices']['eyes'] = ['Neon']
        with self.assertRaisesRegex(ValueError, 'valid unique Roblox materials'):
            normalize_character_creation(invalid)

    def test_migration_keeps_authored_points_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            (base/'assets/manifests').mkdir(parents=True)
            (base/'src/shared').mkdir(parents=True)
            data = json.loads((ROOT/'assets/manifests/options.json').read_text(encoding='utf8'))
            data['characterCreation'].pop('colorPresets', None)
            data['characterCreation'].pop('materialChoices', None)
            from services.character_creation_settings import DEFAULTS as CREATION_DEFAULTS
            data['characterCreation'].setdefault('spawnPoints', deepcopy(CREATION_DEFAULTS['spawnPoints']))
            data['characterCreation']['spawnPoints']['male']['position'] = [119.,-99.,12.]
            path = base/'assets/manifests/options.json'
            path.write_text(json.dumps(data),encoding='utf8')
            result = migrate(base)
            self.assertEqual(result['spawnPoints']['male']['position'], [119.,-99.,12.])
            self.assertEqual(result['colorPresets'],DEFAULTS['colorPresets'])
            self.assertIn('materialChoices = table.freeze({', (base/'src/shared/GameOptionsRegistry.luau').read_text())
            self.assertEqual(len(list(path.parent.glob('options.json.pre-m482-*.bak'))),1)
            self.assertEqual(migrate(base),result)
            self.assertEqual(len(list(path.parent.glob('options.json.pre-m482-*.bak'))),1)

    def test_preview_hair_mount_is_reused_and_cleaned_up(self):
        mount=(ROOT/'src/client/character/BoneMountedAttachmentController.luau').read_text()
        preview=(ROOT/'src/client/character/CharacterCreationPreviewController.luau').read_text()
        self.assertIn('RegisterPreview(model: Model)', mount)
        self.assertIn('updateCharacter(preview)', mount)
        self.assertIn('Mounts.RegisterPreview(instance)', preview)
        self.assertIn('Mounts.UnregisterPreview(previous)', preview)
        self.assertIn('Mounts.UnregisterPreview(model)', preview)
        self.assertNotIn('RunService.RenderStepped:Connect', preview)

    def test_streaming_focus_is_server_owned_and_released(self):
        streaming=(ROOT/'src/server/character/CharacterCreationStreamingService.luau').read_text()
        self.assertIn('player:AddReplicationFocus(focus)', streaming)
        self.assertIn('player:RequestStreamAroundAsync(midpoint, 6)', streaming)
        self.assertIn('player:RemoveReplicationFocus(focus)', streaming)
        self.assertIn('CharacterCreationPending', streaming)
        self.assertIn('CanCollide = false', streaming)
        service=(ROOT/'src/server/character/CharacterService.luau').read_text()
        self.assertIn('CharacterCreationStreamingService.Start',service)

    def test_one_variant_hides_variant_grid_but_preserves_color_material(self):
        view=(ROOT/'src/client/character/CharacterCreationAppearanceView.luau').read_text()
        panel=(ROOT/'src/client/character/CharacterCreationPanel.luau').read_text()
        controller=(ROOT/'src/client/character/CharacterCreationController.luau').read_text()
        self.assertIn('if #entries > 1 then', view)
        self.assertIn('materialPicker(root', view)
        self.assertIn('colorPicker(root', view)
        self.assertIn('visible[category] = #entries > 1 or (#entries == 1 and (category ~= "head"', controller)
        self.assertIn('button.Visible = visible[key] == true', panel)
        self.assertIn('palette:Open',controller)
        overlay=(ROOT/'src/client/character/CharacterCreationColorPalette.luau').read_text()
        self.assertIn('Color3.fromHSV',overlay)
        self.assertIn('HexColorInput',overlay)
        self.assertIn('ColorPaletteOverlay',overlay)

    def test_server_enforces_material_and_preserves_playable_recipe(self):
        service=(ROOT/'src/server/character/CharacterCreationAppearanceService.luau').read_text()
        self.assertIn('unknown_material_channel',service)
        self.assertIn('invalid_" .. group .. "_material',service)
        self.assertIn('recipe.parts.hair.material = selectedMaterials.hair',service)
        self.assertIn('selectedMaterials.eyes',service)
        self.assertIn('selected.materials = selectedMaterials',service)
        preview=(ROOT/'src/client/character/CharacterCreationPreviewController.luau').read_text()
        self.assertIn('applyMaterials(instance, choice.materials or {})',preview)

    def test_game_text_all_languages(self):
        from localization.catalog import read_catalog, LOCALES
        data=read_catalog(ROOT)
        for key in ('creation.hair_material','creation.eyes_material','creation.custom_color',
                    'creation.palette_apply','creation.palette_cancel'):
            self.assertEqual(set(data['groups']['creation'][key]['translations']),set(LOCALES))


if __name__ == '__main__': unittest.main()
