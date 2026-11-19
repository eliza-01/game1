"""M385a: house Collision Blueprint must be visible, selectable, and not break Real Estate."""
from __future__ import annotations

import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / 'system/control-center/static'


class HouseCollisionMarkup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.collisions = []
        self.publish_section = False
        self.house_actions = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        element = (tag, attrs.get('id'), attrs.get('class', ''))
        self.stack.append(element)
        if attrs.get('id') == 'house-collision-panel':
            self.collisions.append(tuple(self.stack))
        if attrs.get('id') and attrs['id'].startswith('house-collision-'):
            self.house_actions.add(attrs['id'])

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break


class HouseCollisionUiM385a(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = (STATIC / 'index.html').read_text(encoding='utf-8')
        cls.estate = (STATIC / 'real-estate.js').read_text(encoding='utf-8')
        cls.shared = (STATIC / 'location-collision.js').read_text(encoding='utf-8')

    def test_collision_editor_visible_above_the_registered_houses_library(self):
        html = HouseCollisionMarkup()
        html.feed(self.page)
        self.assertEqual(len(html.collisions), 1)
        ancestors = html.collisions[0]
        self.assertTrue(any('panel character-card' in classes for _tag, _id, classes in ancestors))
        self.assertLess(self.page.index('id="house-collision-panel"'), self.page.index('class="real-estate-library"'))
        for action in ('asset', 'validate', 'capture', 'preview', 'clear', 'status', 'meta', 'history'):
            self.assertIn('house-collision-' + action, html.house_actions)

    def test_registered_house_row_contains_an_action_matching_its_handler(self):
        render = self.estate.split('function realEstateRender(){', 1)[1].split('async function realEstateLoad()', 1)[0]
        row_template = render.split('return `<tr class=', 1)[1].split('`;', 1)[0]
        self.assertEqual(row_template.count('data-re-collision'), 1)
        self.assertEqual(len(re.findall(r"tr\.querySelector\('\[data-re-collision\]'\)\.onclick", render)), 1)
        self.assertIn('window.game1RealEstateCollisionSelect?.(row.slug)', render)

    def test_selecting_a_house_updates_blueprint_without_forced_scrolling(self):
        self.assertIn("window.game1RealEstateCollisionSelect?.(row?.slug||'', false)", self.estate)
        self.assertIn('select(slug, scroll=true)', self.shared)
        self.assertIn('if (state.slug!==target)', self.shared)
        self.assertIn('if (scroll) get(`${prefix}-panel`).scrollIntoView', self.shared)
        self.assertIn('game1RealEstateCollisionRefresh(snapshot.items)', self.estate)
        self.assertIn('real-estate.js?v=385a', self.page)
        self.assertIn('real-estate.css?v=385a', self.page)

    def test_location_assets_still_use_shared_blueprint_editor(self):
        self.assertIn("attach('location-collision','location-assets'", self.shared)
        self.assertIn("attach('house-collision','real-estate'", self.shared)
        self.assertIn('window.game1LocationCollisionSelect=location.select', self.shared)
        self.assertIn('window.game1RealEstateCollisionSelect=house.select', self.shared)


if __name__ == '__main__':
    unittest.main()
