"""M198 Characters-only UI order, modal registration, atlas families and ranks."""
from html.parser import HTMLParser
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / 'system/control-center/static'


class Markup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parents = []
        self.found = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.found[attrs['id']] = (tag, tuple(self.parents))
        if tag not in {'link', 'input', 'br', 'meta', 'img', 'hr'}:
            self.parents.append(tag)

    def handle_endtag(self, tag):
        if tag in self.parents:
            i = len(self.parents) - 1 - self.parents[::-1].index(tag)
            del self.parents[i:]


class CharacterAtlasPresentationM198(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (STATIC / 'index.html').read_text(encoding='utf8')
        cls.components = (STATIC / 'character-components.js').read_text(encoding='utf8')

    def test_registration_is_one_button_within_inspection_dialog(self):
        markup = Markup()
        markup.feed(self.html)
        self.assertNotIn('cp-register', markup.found)
        self.assertIn('dialog', markup.found['cp-confirm'][1])
        self.assertLess(self.html.index('id="cp-choose"'), self.html.index('id="cp-conflict"'))
        self.assertIn("const approval=await approve();", self.components)
        self.assertIn("await post(base+'/register'", self.components)

    def test_publish_selected_below_table_on_right(self):
        table = self.html.index('id="cp-table"')
        bottom = self.html.index('id="cp-publish-all"')
        atlases = self.html.index('class="cp-atlas-section"')
        self.assertLess(table, bottom)
        self.assertLess(bottom, atlases)
        self.assertIn('<div class="cp-publish-bulk"><button id="cp-publish-all"', self.html)
        self.assertIn('justify-content:flex-end', (STATIC / 'character-components.css').read_text())

    def test_presentation_scripts_loaded_before_consumers(self):
        start = self.html.index('character-atlas-presentation.js?v=1')
        self.assertLess(start, self.html.index('character-components.js?v=12'))
        self.assertLess(start, self.html.index('character-atlas-ui.js?v=2'))

    @unittest.skipUnless(shutil.which('node'), 'Node required for browser integration simulation')
    def test_ranked_options_render_and_unpublished_first(self):
        result = subprocess.run([shutil.which('node'),
            str(ROOT / 'system/verify/character_atlas_presentation_m198.js'),
            str(STATIC / 'character-atlas-presentation.js'),
            str(STATIC / 'character-components.js'),
            str(STATIC / 'character-atlas-ui.js')],
            text=True, capture_output=True, timeout=25)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('unpublished-first passed', result.stdout)
