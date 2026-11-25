"""M493 face material catalog, Options migration and shared client/server contracts."""
from pathlib import Path
from copy import deepcopy
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'system/control-center'))
from services.character_creation_settings import DEFAULTS, normalize_character_creation
from options_store import OptionsStore
from localization.catalog import read_catalog, LOCALES

MATERIALS = ['Plastic', 'Slate', 'Fabric', 'SmoothPlastic', 'Sandstone', 'Grass', 'LeafyGrass', 'Concrete']
GROUPS = ('hair', 'eyes', 'eyebrows', 'head')


def source(path):
    return (ROOT / path).read_text(encoding='utf8')


class FaceMaterialsM493(unittest.TestCase):
    def test_order_and_export(self):
        expected = {group: MATERIALS for group in GROUPS}
        self.assertEqual(DEFAULTS['materialChoices'], expected)
        data = json.loads(source('assets/manifests/options.json'))
        self.assertEqual(data['characterCreation']['materialChoices'], expected)
        registry = source('src/shared/GameOptionsRegistry.luau')
        for group in GROUPS:
            self.assertIn(group + ' = table.freeze({' + ', '.join(map(json.dumps, MATERIALS)) + '})', registry)
            self.assertEqual(set(read_catalog(ROOT)['groups']['creation']['creation.'+group+'_material']['translations']), set(LOCALES))

    def test_old_options_upgrade_preserves_other_fields(self):
        data = json.loads(source('assets/manifests/options.json'))
        creation = data['characterCreation']
        creation['spawnPoints']['male']['position'] = [19., 22., 31.]
        creation['materialChoices'] = {'hair':['Plastic','Sand'], 'eyes':['Plastic','Metal']}
        expected = deepcopy(data)
        expected['characterCreation']['materialChoices'] = deepcopy(DEFAULTS['materialChoices'])
        expected['characterCreation'].setdefault('animations', deepcopy(DEFAULTS['animations']))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root/'assets/manifests/options.json'
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(data), encoding='utf8')
            (path.parent/'location-assets.json').write_text(source('assets/manifests/location-assets.json'), encoding='utf8')
            snapshot = OptionsStore(root).snapshot()
            self.assertEqual(snapshot['characterCreation'], expected['characterCreation'])
            self.assertEqual(OptionsStore(root).snapshot(), snapshot)

    def test_rejects_invalid_new_materials(self):
        for invalid in ('Metal','Glass','Neon','Sand','FakeMaterial',{},None):
            changed = deepcopy(DEFAULTS['materialChoices'])
            changed['head'] = ['Plastic',invalid]
            with self.assertRaises(ValueError):
                normalize_character_creation({'materialChoices':changed})

    def test_picker_and_live_preview_use_every_group(self):
        view = source('src/client/character/CharacterCreationAppearanceView.luau')
        self.assertIn('grid.FillDirectionMaxCells = 3', view)
        self.assertIn('tostring(i), list)', view)
        self.assertIn('(selectedIndex - 1 + delta) % #materials + 1', view)
        self.assertNotIn('nameButton.Activated:Connect', view)
        self.assertIn('list.Visible = true', view)
        self.assertIn('onMaterial(group, value)', view)
        self.assertEqual(view.count('materialPicker(root,'), 1)
        controller = source('src/client/character/CharacterCreationController.luau')
        self.assertIn('FaceMaterials.Groups', controller)
        self.assertIn('visible[category] = #entries > 0', controller)
        # M498 hides the head tab only; the four-group material contract remains.
        self.assertIn('local TABS = table.freeze({"hair", "eyebrows", "eyes"})',
                      source('src/client/character/CharacterCreationPanel.luau'))
        preview = source('src/client/character/CharacterCreationPreviewController.luau')
        self.assertIn('FaceMaterials.GroupForPart(slot, channel)', preview)
        contract = source('src/shared/character/CharacterCreationMaterials.luau')
        for fragment in ('eye_l = "eyes"','eye_r = "eyes"','eyebrow_l = "eyebrows"','eyebrow_r = "eyebrows"','head = "head"','return "hair"'):
            self.assertIn(fragment, contract)

    def test_saved_profile_compatibility_is_server_only(self):
        gateway = source('src/server/character/CharacterCreationGateway.luau')
        service = source('src/server/character/CharacterCreationAppearanceService.luau')
        self.assertIn('self.validate(archetypeId, appearance)', gateway)
        self.assertIn('self.validate(record.archetype, record.appearance, true)', gateway)
        self.assertIn('if savedProfile and type(material) == "string"', service)
        self.assertIn('selectedMaterials[slot]', service)
        self.assertIn('selectedMaterials.eyebrows', service)
        self.assertIn('selected.materials = selectedMaterials', service)
        self.assertNotIn('savedProfile', source('src/server/character/CharacterCreationPreviewService.luau'))


if __name__ == '__main__':
    unittest.main()
