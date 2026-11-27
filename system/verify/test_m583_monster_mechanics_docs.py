"""M583/M584: current monster navigation is discoverable via the existing Mechanics API."""
import sys
import unittest
from pathlib import Path
from urllib.parse import urlencode, urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from api.mechanics import route
from mechanics.catalog import permitted_source


class MonsterMechanicsM583(unittest.TestCase):
    def setUp(self):
        status, catalog = route(urlparse('/api/mechanics'))
        self.assertEqual(status, 200)
        self.domain = next(d for d in catalog['domains'] if d['id'] == 'monster')
        self.card = next(c for c in self.domain['items'] if c['id'] == 'monster-ai-pursuit')
        self.sections = {s['title']: ' '.join(s['lines']) for s in self.card['sections']}

    def test_existing_shared_card_covers_current_navigation(self):
        self.assertEqual(len(self.domain['items']), 3)
        self.assertEqual(self.card['scope'], 'shared')
        cases = {
            'Aggro и границы преследования': ('Home Leash', 'Death Chase', '30 с'),
            'Experimental Navigation · область действия': ('Только Studio', 'Legacy', '1,5 с'),
            'Climb · физический прыжок M578/M580': ('1 секундой', 'Приземление', 'план сбрасывается'),
            'Rescue Routes · авторинг и вход M590': ('свободные начало и конец', 'Route connection height', 'по умолчанию 2 studs', 'Rojo Sync', 'без порога длины', '40 studs', '2 studs', '20 studs', '4 studs', 'ближайшая доступная 3D-проекция', 'единственный луч от пяток', 'FootBlocked'),
            'Rescue Routes · выбор выхода M582/M586': ('3D-дистанция', 'не превышает исходное', 'промежуточные точки', 'перепад высоты', '32 интервалов'),
            'StuckTimeout · аварийный возврат M580': ('20 с', '1,05 с', 'ID и HP', 'неуязвима'),
            'Диагностика Studio Play': ('MONNAV', 'GRAPH_SEARCH', 'HOME_RECALL_OUT'),
            'Недостающее / проверка': ('Terrain', 'Studio Play', 'опубликованного runtime'),
        }
        for section, phrases in cases.items():
            for phrase in phrases:
                self.assertIn(phrase, self.sections[section], section)

    def test_all_card_sources_are_readable_and_scoped(self):
        sources = {s['id']: s for s in self.card['sources']}
        self.assertTrue({'monster-rescue-graph', 'monster-climb', 'monster-home-recall',
                         'monster-nav-dispatch', 'monster-gameplay-doc',
                         'monster-rescue-topology', 'monster-rescue-segments', 'monster-rescue-routes',
                         'monster-rescue-connections', 'monster-rescue-sampling', 'monster-rescue-entries', 'monster-rescue-exits', 'monster-rescue-paths', 'monster-rescue-queries'} <= sources.keys())
        for key, source in sources.items():
            with self.subTest(source=key):
                self.assertTrue((ROOT / source['path']).is_file())
                self.assertEqual(permitted_source(self.card['id'], key)[0], source['path'])
                status, payload = route(urlparse('/api/mechanics/source?' + urlencode(
                    {'item': self.card['id'], 'source': key})))
                self.assertEqual(status, 200)
                self.assertEqual(payload['path'], source['path'])
                self.assertTrue(payload['content'])
        self.assertIsNone(permitted_source('monster-attack-visuals', 'monster-rescue-graph'))
        self.assertIsNone(permitted_source(self.card['id'], '../../.env'))
