"""M177: compact Characters status and a non-destructive publication queue."""
from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

STATIC = Path(__file__).resolve().parents[1] / 'control-center' / 'static'


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.by_id = {}
        self.classes = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a:
            self.by_id[a['id']] = (tag, a)
        self.classes.extend((a.get('class') or '').split())


class CharacterCompactUiM177(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (STATIC / 'index.html').read_text('utf-8')
        cls.css = (STATIC / 'character-components.css').read_text('utf-8')
        cls.summary = (STATIC / 'character-component-summary.js').read_text('utf-8')
        cls.components = (STATIC / 'character-components.js').read_text('utf-8')
        cls.publications = (STATIC / 'character-publications.js').read_text('utf-8')

    def test_remove_redundant_english_intro_and_workflow_links(self):
        self.assertNotIn('Register reusable parts, publish only changed meshes', self.html)
        self.assertNotIn('class="character-flow-nav"', self.html)
        self.assertNotIn('.character-flow-nav', self.css)
        self.assertNotIn('Inspect the FBX first: registration creates each named part', self.html)

    def test_summary_live_and_accessible_with_russian_advice_and_warning(self):
        tags = Tags(); tags.feed(self.html)
        self.assertEqual(tags.by_id['cp-counts'][0], 'div')
        self.assertEqual(tags.by_id['cp-flow-summary'][1]['role'], 'status')
        for s in ('Риги', 'Части', 'Сеты', 'Опубликовано', 'К публикации',
                  'Совет:', 'Внимание:', 'Старые Model ID сохраняются'):
            self.assertIn(s, self.summary)
        self.assertIn('catalog?.items||[]', self.summary)
        self.assertIn('replaceChildren(', self.summary)
        self.assertNotIn('innerHTML', self.summary)
        self.assertIn('window.game1CharacterComponentSummary.render(catalog)', self.components)
        self.assertLess(self.html.index('character-component-summary.js?v=1'),
                        self.html.index('character-components.js?v=5'))

    def test_naming_and_starting_stats_open_by_default(self):
        self.assertRegex(self.html, r'<details open><summary>Mesh naming standard</summary>')
        self.assertRegex(self.html, r'<details class="ca-stats" open><summary>Starting stats</summary>')
        self.assertIn('fullplate_imperial_upper_', self.html)  # M175 guide kept

    def test_queue_stays_visible_and_shows_selected_before_first_upload(self):
        tags = Tags(); tags.feed(self.html)
        self.assertIn('cp-publication-open', tags.by_id)
        self.assertNotIn('hidden', tags.by_id['cp-publication-open'][1])
        self.assertIn('cp-queue-button', tags.classes)
        self.assertIn("queueButton.classList.toggle('cp-queue-alert',queued>0)", self.publications)
        self.assertIn('function renderSelectionPreview()', self.publications)
        self.assertIn('selected.has(key(row))&&eligible(row)', self.publications)
        self.assertIn('if(!active()&&selected.size)renderSelectionPreview();', self.publications)
        self.assertIn('prefers-reduced-motion:reduce', self.css)
        self.assertIn('@keyframes cp-queue-pulse', self.css)
        self.assertIn('#3cbfbd', self.css)
        self.assertNotIn("el('publication-open').hidden=!job", self.publications)

    def test_no_runtime_schema_or_publish_endpoint_changes(self):
        self.assertIn("const base='/api/characters/components/publication-queue'", self.publications)
        self.assertIn("const base='/api/characters/components'", self.components)
        self.assertIn('window.game1CharacterPublications.configure(catalog,busy)', self.components)


if __name__ == '__main__':
    unittest.main()
