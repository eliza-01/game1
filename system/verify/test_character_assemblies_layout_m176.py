"""M176: modular character UX layout and draft safety contracts."""
from html.parser import HTMLParser
from pathlib import Path
import unittest

STATIC = Path(__file__).resolve().parents[1] / 'control-center' / 'static'


class Markup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.starts = []
        self.hints = []

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        if attr.get('id'):
            self.starts.append(attr['id'])
        if attr.get('data-character-tip'):
            self.hints.append(attr['data-character-tip'])


class CharacterAssembliesLayoutM176(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (STATIC / 'index.html').read_text(encoding='utf8')
        cls.js = (STATIC / 'character-assemblies.js').read_text(encoding='utf8')
        cls.legacy = (STATIC / 'character-assets.js').read_text(encoding='utf8')
        cls.css = (STATIC / 'character-assemblies.css').read_text(encoding='utf8')

    def test_registry_before_editor_and_unique_new_action(self):
        self.assertLess(self.html.index('id="ca-rows"'), self.html.index('id="ca-editor-section"'))
        self.assertLess(self.html.index('id="ca-new"'), self.html.index('id="ca-rows"'))
        self.assertLess(self.html.index('id="ca-editor-section"'), self.html.index('id="ca-save"'))
        html = Markup()
        html.feed(self.html)
        self.assertEqual(len(html.starts), len(set(html.starts)))
        self.assertEqual(html.starts.count('ca-new'), 1)
        self.assertNotIn('new-character', html.starts)  # No duplicate create action in the rail.

    def test_two_columns_with_independent_slot_order(self):
        self.assertIn("parts:['head','upper','lower','gloves','boots']", self.js)
        self.assertIn("parts:['hair','eyebrows','eyes']", self.js)
        self.assertIn('ca-part-column', self.js)
        self.assertIn('grid-template-columns:repeat(2,minmax(0,1fr))', self.css)
        # Keep existing transport order (first four are clothing); only UI order changes.
        self.assertIn("const clothing = slots.slice(0,4);", self.js)

    def test_new_draft_clears_all_parts_without_implicit_set(self):
        body = self.js.split('function newDraft(){', 1)[1].split('\n  function render(){', 1)[0]
        self.assertIn("fillSets('');", body)
        self.assertIn("chooseParts(Object.fromEntries(slots.map(s=>[s,''])));", body)
        self.assertNotIn('applySet()', body)
        self.assertNotIn("get('slot-head').value=", body)
        self.assertNotIn("get('slot-hair').value=", body)
        self.assertIn('original=JSON.stringify(form());', body)

    def test_status_readable_and_startup_noninteractive(self):
        self.assertIn('Черновик · требуется исправить:', self.js)
        self.assertIn('Одежда · смешанный комплект', self.js)
        self.assertIn('ca-outfit-incomplete', self.js)
        self.assertIn("node('span','✓ startup')", self.js)
        self.assertIn('character-startup-badge', self.html)
        self.assertIn('ca-stats{', self.css)
        self.assertIn('character-needs-publish{border:', self.css)
        self.assertIn('activateButton=tr.querySelector', self.legacy)

    def test_character_help_text_in_russian(self):
        html = Markup()
        html.feed(self.html)
        self.assertGreaterEqual(len(html.hints), 6)
        for tip in html.hints:
            self.assertRegex(tip, r'[А-Яа-яЁё]', f'Character tooltip is not Russian: {tip[:60]}')
            self.assertLess(len(tip), 1300)


if __name__ == '__main__':
    unittest.main()
