"""Favorites are revisioned metadata; design is planning, not gameplay state."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from kanban_store import KanbanError, KanbanStore
from api import kanban


class KanbanFavoritesM537(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.store = KanbanStore(self.root)
        self.first = self.store.create({'title': 'First work'})['card']
        self.second = self.store.create({'title': 'Second work'})['card']

    def update(self, card, **payload):
        return self.store.update(card['id'], {'expectedRevision': card['revision'], **payload})['card']

    def test_pin_unpin_persistence_export_noop_and_revision(self):
        old = self.store.detail(self.second['id'])
        pinned = self.update(self.second, action='favorite', favorite=True)
        self.assertTrue(KanbanStore(self.root).detail(pinned['id'])['card']['favorite'])
        self.assertEqual(pinned['revision'], 2)
        self.assertEqual(old['spec'], self.store.detail(pinned['id'])['spec'])
        self.assertEqual(pinned['specSha256'], self.second['specSha256'])
        self.assertEqual(self.update(pinned, action='favorite', favorite=True), pinned)
        self.assertEqual(len(self.store.history_for(pinned['id'])['events']), 1)
        self.assertEqual(self.store.history_for(pinned['id'])['events'][0]['action'], 'favorite')
        self.assertEqual(len(list((self.store.backups / pinned['id']).iterdir())), 1)
        self.assertIn('## ★ KBN-0002', self.store.export()['markdown'])
        self.assertLess(self.store.export()['markdown'].index('KBN-0002'), self.store.export()['markdown'].index('KBN-0001'))
        self.assertEqual([c['id'] for c in self.store.list_cards()['cards']], ['KBN-0001', 'KBN-0002'])
        status, _ = kanban.write('/api/kanban/KBN-0002', lambda: {'expectedRevision': 1, 'action': 'favorite', 'favorite': False}, {'kanban': self.store})
        self.assertEqual(status, 409)
        unpinned = self.update(pinned, action='favorite', favorite=False)
        self.assertFalse(unpinned['favorite'])
        self.assertLess(self.store.export()['markdown'].index('KBN-0001'), self.store.export()['markdown'].index('KBN-0002'))

    def test_missing_field_and_validation(self):
        file = self.store.cards / 'KBN-0001.json'
        old = dict(self.first)
        old.pop('favorite')
        file.write_text(json.dumps(old), encoding='utf-8')
        self.assertEqual(self.store.detail(old['id'])['card'], old)
        for value in ('true', 1, None, []):
            with self.assertRaises(KanbanError):
                self.update(old, action='favorite', favorite=value)
        self.assertEqual(self.update(old, action='favorite', favorite=False), old)
        self.assertTrue(self.update(old, action='favorite', favorite=True)['favorite'])
        old['favorite'] = 'false'
        file.write_text(json.dumps(old), encoding='utf-8')
        with self.assertRaisesRegex(KanbanError, 'favorite contract'):
            self.store.detail(old['id'])

    def test_done_card_can_pin_but_cannot_edit_contract(self):
        card = self.update(self.first, action='task', itemId='KBN-0001-T01', done=True)
        card = self.update(card, action='acceptance', itemId='KBN-0001-A01', status='PASS', evidence='Fixture test')
        card = self.update(card, action='status', status='DONE')
        pinned = self.update(card, action='favorite', favorite=True)
        self.assertEqual(pinned['status'], 'DONE')
        self.assertEqual(pinned['tasks'], card['tasks'])
        self.assertEqual(pinned['acceptance'], card['acceptance'])
        with self.assertRaises(KanbanError):
            self.update(pinned, action='task', itemId='KBN-0001-T01', done=False)

    def test_design_contract_and_navigation(self):
        data = KanbanStore(ROOT).detail('KBN-0031')
        self.assertEqual(data['card']['title'], 'Design')
        self.assertEqual(data['card']['domain'], 'Design')
        for term in ('Any', '1–4', '5–9', '10–14', '25–30', 'Карта', 'D+', 'без классов', 'Armor Crush', 'Shackle Shot'):
            self.assertIn(term, data['spec'])
        import re
        levels = re.findall(r'^\| (\d+) \| (\d+) \| [^|]+ \|', data['spec'], re.M)
        self.assertEqual([int(l) for l, _ in levels], list(range(1,31)))
        self.assertEqual(int(levels[-1][1]), 630)
        self.assertTrue(all(int(a[1]) < int(b[1]) for a,b in zip(levels,levels[1:])))
        for identifier in ('KBN-0027','KBN-0029'):
            self.assertIn('KBN-0031.md', KanbanStore(ROOT).detail(identifier)['spec'])
        html = (ROOT/'system/control-center/static/index.html').read_text('utf-8')
        self.assertIn('kanban.js?v=539', html)
        self.assertIn('kanban.css?v=539', html)


if __name__ == '__main__':
    unittest.main()
