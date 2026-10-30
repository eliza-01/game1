"""M173 UI contracts: modular pipeline order, legacy safety and controls."""
from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

STATIC = Path(__file__).resolve().parents[1] / 'control-center' / 'static'


class Markup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.anchors = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if attributes.get('id'):
            self.ids.append(attributes['id'])
        if tag == 'a' and attributes.get('href', '').startswith('#'):
            self.anchors.append(attributes['href'][1:])


class CharacterModularUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (STATIC / 'index.html').read_text(encoding='utf8')
        cls.components = (STATIC / 'character-components.js').read_text(encoding='utf8')
        cls.assemblies = (STATIC / 'character-assemblies.js').read_text(encoding='utf8')

    def test_guided_pipeline_order_and_links(self):
        self.assertLess(self.html.index('id="character-components-panel"'),
                        self.html.index('id="character-assemblies-panel"'))
        self.assertLess(self.html.index('id="cp-publication-step"'),
                        self.html.index('id="character-assemblies-panel"'))
        markup = Markup()
        markup.feed(self.html)
        self.assertEqual(len(markup.ids), len(set(markup.ids)))
        for anchor in ('character-components-panel', 'cp-publication-step',
                       'character-assemblies-panel', 'ca-rows'):
            self.assertIn(anchor, markup.anchors)
            self.assertIn(anchor, markup.ids)

    def test_legacy_publication_is_separate_and_not_migrated_by_ui(self):
        self.assertIn('class="cp-legacy"', self.html)
        self.assertIn('no automatic migration', self.html)
        self.assertIn('id="register-character"', self.html)
        self.assertIn('id="cp-register"', self.html)
        self.assertIn("'/api/characters/assemblies'", self.assemblies)
        self.assertNotIn('replace-model', self.assemblies)
        self.assertNotIn('/publish', self.assemblies)

    def test_outfit_gender_publication_and_draft_controls(self):
        for element in ('ca-editor-summary','ca-mix','ca-readiness','ca-reset','ca-save'):
            self.assertIn(f'id="{element}"', self.html)
        for token in ('row.gender===\'common\'','row.gender===gender',
                      "const clothing = slots.slice(0,4)",
                      "window.confirm('Отменить несохранённые", 'expected_revision:editRevision',
                      "resolved.missing", 'original=JSON.stringify(form())'):
            self.assertIn(token, self.assemblies)
        self.assertIn("role==='part'", self.assemblies)
        self.assertIn('Save recipe &amp; starting stats', self.html)

    def test_inspection_and_component_publication_stay_separate(self):
        self.assertIn('New clothing sets created on Register', self.components)
        self.assertIn("plan.new_sets", self.components)
        self.assertIn("plan.conflicts", self.components)
        self.assertIn('Publish selected', self.html)
        self.assertIn('Published revisions remain assigned during replacement', self.components)
        self.assertIn('No Roblox Model Asset was uploaded', self.components)


if __name__ == '__main__':
    unittest.main()
