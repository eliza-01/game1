"""M479: authored five-view character creation contract and safe spawn gateway."""
import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services.character_creation_settings import (
    DEFAULTS, VIEW_NAMES, normalize_character_creation,
)
from options_store import OptionsStore
from localization.catalog import read_catalog


class CharacterCreationM479(unittest.TestCase):
    def test_exact_five_studio_views_with_authoritative_order(self):
        self.assertEqual(VIEW_NAMES, (
            'SelectionOverview', 'MaleFullBody', 'FemaleFullBody', 'MaleFace', 'FemaleFace'))
        self.assertEqual(list(DEFAULTS['views']), list(VIEW_NAMES))
        self.assertFalse(DEFAULTS['enabled'])
        self.assertTrue(DEFAULTS['useStudioAnchors'])
        normalized = normalize_character_creation(DEFAULTS)
        self.assertEqual(normalized['views']['SelectionOverview']['fov'], 70)
        self.assertAlmostEqual(normalized['views']['MaleFace']['cframe'][0], 180.331024)
        self.assertAlmostEqual(normalized['views']['FemaleFace']['cframe'][0], 182.726929)

    def test_settings_are_strict_and_validate_camera_geometry(self):
        for change in ({'enabled': 1}, {'enabled': 'true'}, {'nonsense': True},
                       {'transitionSeconds': 0}, {'faceTransitionSeconds': float('inf')},
                       {'desktopPanelWidthPx': 240.5}, {'mobilePanelWidthPx': 900},
                       {'views': {}}, {'views': {'SelectionOverview': {}}}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                normalize_character_creation(change)
        base = deepcopy(DEFAULTS)
        base['views']['MaleFace']['cframe'][3] = 5
        with self.assertRaisesRegex(ValueError, 'orthonormal'):
            normalize_character_creation(base)
        base = deepcopy(DEFAULTS)
        base['views']['FemaleFace']['fov'] = 110
        with self.assertRaisesRegex(ValueError, 'fov'):
            normalize_character_creation(base)

    def test_options_persist_generate_runtime_and_preserve_unrelated_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / 'assets/manifests'
            folder.mkdir(parents=True)
            for name in ('options.json', 'location-assets.json'):
                (folder / name).write_bytes((ROOT / 'assets/manifests' / name).read_bytes())
            store = OptionsStore(root)
            before = store.snapshot()
            changed = store.update({'characterCreation': {'enabled': True, 'transitionSeconds': 1.25}})
            self.assertTrue(changed['characterCreation']['enabled'])
            self.assertEqual(changed['characterCreation']['transitionSeconds'], 1.25)
            self.assertEqual(changed['characterCreation']['views'], before['characterCreation']['views'])
            for key in ('camera', 'flora', 'rotations', 'socketRanges', 'healthUi'):
                self.assertEqual(changed[key], before[key])
            runtime = (root / 'src/shared/GameOptionsRegistry.luau').read_text(encoding='utf-8')
            self.assertIn('characterCreation = table.freeze({', runtime)
            for view in VIEW_NAMES:
                self.assertIn(view + ' = table.freeze({', runtime)
            self.assertTrue(OptionsStore(root).snapshot()['characterCreation']['enabled'])
            with self.assertRaises(ValueError):
                store.update({'characterCreation': {'transitionSeconds': 100}})
            self.assertEqual(store.snapshot()['characterCreation']['transitionSeconds'], 1.25)

    def test_runtime_has_separated_camera_and_server_selection_ownership(self):
        camera = (ROOT / 'src/client/character/CameraController.luau').read_text()
        ui = (ROOT / 'src/client/character/CharacterCreationController.luau').read_text()
        gateway = (ROOT / 'src/server/character/CharacterCreationGateway.luau').read_text()
        service = (ROOT / 'src/server/character/CharacterService.luau').read_text()
        html = (ROOT / 'system/control-center/static/index.html').read_text()
        self.assertIn('CameraController.ShowCreationView', camera)
        self.assertIn('if creationView then', camera)
        self.assertNotIn('Instance.new("Camera")', ui + camera)
        self.assertIn('CharacterCreationPending', gateway)
        self.assertIn('self.pending[player]', gateway)
        self.assertIn('CharacterCreationEnter', gateway)
        self.assertIn('self.available(archetypeId)', gateway)
        self.assertIn('CharacterCreationGateway.new', service)
        self.assertIn('CharacterCreationSelect', ui)
        self.assertIn('CameraController.ClearCreationView()', ui)
        self.assertIn('option-character-creation-section', html)
        self.assertIn('character-creation-options.js?v=482', html)
        self.assertLess(html.index('SelectionOverview') if 'SelectionOverview' in html else 0,
                        html.index('option-rotation-save'))

    def test_creation_labels_are_translated_in_all_ten_locales(self):
        catalog = read_catalog(ROOT)
        phrases = catalog['groups']['creation']
        self.assertGreaterEqual(len(phrases), 18)
        self.assertIn('creation.hair', phrases)
        self.assertIn('creation.eyebrows_color', phrases)
        for key, value in phrases.items():
            self.assertEqual(set(value['translations']), set(catalog['locales']), key)
        language = (ROOT / 'src/server/localization/PlayerLanguageService.luau').read_text()
        self.assertIn('local storeOk, store = pcall', language)
        self.assertIn('if not store then', language)


if __name__ == '__main__':
    unittest.main()
