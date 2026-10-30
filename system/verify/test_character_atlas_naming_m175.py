"""M175: Character atlas names stay aligned with multiword clothing sets.

The rule is limited to new Character authoring, not the shared AtlasRegistry.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase, mock
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from character_core.part_names import parse_part
from character_core.atlas_authoring import CharacterAtlasAuthoring
from services.texture_atlas_registry import AtlasRegistry, parse_filename


class CharacterAtlasNamingM175(TestCase):
    def setUp(self):
        t = TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        (self.root / 'incoming').mkdir()
        (self.root / '.control-center').mkdir()
        self.registry = AtlasRegistry(self.root)
        self.components = SimpleNamespace(root=self.root, atlases=self.registry, export=mock.Mock())
        self.flow = CharacterAtlasAuthoring(self.components)

    def image(self, name, size=(32, 32)):
        target = self.root / 'incoming' / name
        Image.new('RGB', size, 'green').save(target)
        return target

    def test_multiword_sets_are_parsed_from_last_slot_suffix(self):
        for slot in ('upper', 'lower', 'gloves', 'boots'):
            parsed = parse_part('fullplate_imperial_' + slot)
            self.assertEqual(parsed['set_id'], 'fullplate_imperial')
            self.assertEqual(parsed['slot'], slot)
        with self.assertRaisesRegex(ValueError, 'snake_case'):
            parse_part('fullplate imperial_upper')

    def test_all_eight_slots_plus_shared_and_effect_use_canonical_names(self):
        keys = ['fullplate_imperial_' + s for s in ('upper', 'lower', 'gloves', 'boots')]
        keys += ['fullplate_imperial', 'head_01_male', 'head_01_female', 'hair_01_male',
                 'hair_01_female', 'hair_01_common', 'eyes_01', 'eyebrows_01', 'eyes_01_spiral']
        for key in keys:
            with self.subTest(key=key):
                path = self.image(key + '_32x32_atlas.png')
                data = self.flow.inspect(str(path))
                self.assertTrue(data['valid'], data['reason'])
                self.assertEqual(parse_filename(path.name)['atlasKey'], key)
        self.assertEqual(self.registry.catalog(), [])  # inspect must not register anything

    def test_bad_character_names_suggest_canonical_underscore_name(self):
        cases = [
            ('fullplate imperial_upper_32x32_atlas.png', 'fullplate_imperial_upper_32x32_atlas.png'),
            ('Fullplate_Imperial_upper_32x32_atlas.png', 'fullplate_imperial_upper_32x32_atlas.png'),
            ('fullplate-imperial_upper_32x32_atlas.png', 'fullplate_imperial_upper_32x32_atlas.png'),
            ('123_32x32_atlas.png', 'character_123_32x32_atlas.png'),
        ]
        for source, expected in cases:
            with self.subTest(source=source):
                path = self.image(source)
                info = self.flow.inspect(str(path))
                self.assertFalse(info['valid'])
                self.assertEqual(info['expectedFilename'], expected)
                with self.assertRaisesRegex(ValueError, 'Expected:'):
                    self.flow.publish({'sourcePath': str(path)}, lambda _: {})
        self.assertEqual(self.registry.catalog(), [])

    def test_wrong_dimensions_propose_actual_dimensions_and_canonical_name(self):
        path = self.image('Fullplate Imperial_64x64_atlas.png', (32, 32))
        data = self.flow.inspect(str(path))
        self.assertFalse(data['valid'])
        self.assertIn('dimensions', data['reason'])
        self.assertEqual(data['expectedFilename'], 'fullplate_imperial_32x32_atlas.png')

    def test_shared_registry_keeps_existing_legacy_names(self):
        path = self.image('fullplate imperial_32x32_atlas.png')
        existing = self.registry.register_file(str(path), domain='character')
        self.assertEqual(self.registry.get_variant(existing['id'])['id'], existing['id'])
        self.assertEqual(self.registry.catalog(domain='character')[0]['atlasKey'], 'fullplate imperial')
        self.assertFalse(self.flow.inspect(str(path))['valid'])  # new selection requires new name
        self.assertEqual(self.registry.catalog(domain='character')[0]['atlasKey'], 'fullplate imperial')

    def test_published_replacement_has_no_automatic_new_asset_id(self):
        path = self.image('fullplate_imperial_32x32_atlas.png')
        initial = self.flow.inspect(str(path))
        with mock.patch('services.texture_atlas_registry.create_image_asset', return_value='operations/one'), \
             mock.patch('services.texture_atlas_registry.wait_for_operation',
                        return_value=SimpleNamespace(asset_id='12345', operation_path='operations/one', moderation_state='Approved')):
            self.flow.publish({'sourcePath': str(path), 'sha256': initial['sha256'],
                               'expectedVariantId': 0, 'expectedPublishedId': ''},
                              lambda _: {'apiKey': 'test', 'creatorType':'User', 'creatorId':'1'})
        self.assertEqual(self.flow.inspect(str(path))['existing']['publishedId'], '12345')
        self.assertTrue(self.flow.inspect(str(path))['unchanged'])

    def test_tooltip_precedes_register_and_documents_each_part(self):
        static = ROOT / 'system/control-center/static'
        html = (static / 'index.html').read_text(encoding='utf-8')
        self.assertLess(html.index('id="cp-atlas-naming-guide"'), html.index('id="cp-atlas-register"'))
        for word in ('fullplate_imperial_upper_', 'fullplate_imperial_lower_',
                     'fullplate_imperial_gloves_', 'fullplate_imperial_boots_',
                     'head_01_male_', 'head_01_female_', 'hair_01_common_',
                     'eyes_01_', 'eyebrows_01_', 'eyes_01_spiral_'):
            self.assertIn(word, html)
        self.assertIn('character-tooltip-atlas', (static/'character-workflow.js').read_text())
        self.assertIn('white-space:pre-line', (static/'character-components.css').read_text())

if __name__ == '__main__':
    import unittest
    unittest.main()
