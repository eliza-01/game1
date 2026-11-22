"""M439 documentation re-baseline: source-backed Kanban, without fabricated Studio PASS."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import shutil
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / 'docs' / 'kanban'

sys.path.insert(0, str(ROOT / 'system' / 'control-center'))
from kanban_store import KanbanStore


class KanbanReconciliationM439(unittest.TestCase):
    def test_all_cards_load_and_export_with_verified_sha(self):
        store = KanbanStore(ROOT)
        cards = store.list_cards()['cards']
        self.assertGreaterEqual(len(cards), 17)
        self.assertEqual([item['id'] for item in cards], sorted(item['id'] for item in cards))
        export = store.export()['markdown']
        for card in cards:
            detail = store.detail(card['id'])
            self.assertIn(card['id'], export)
            self.assertIn('## Текущая сверка · 22.11.2026', detail['spec'])
            actual_hash = hashlib.sha256(detail['spec'].encode('utf-8')).hexdigest()
            self.assertEqual(card['specSha256'], actual_hash)
            self.assertEqual(card['specPath'], f'docs/kanban/specs/{card["id"]}.md')
            if card['status'] == 'DONE':
                self.assertTrue(all(t['done'] for t in card['tasks']))
                self.assertTrue(all(a['status'] == 'PASS' and a.get('evidence')
                                    for a in card['acceptance']))

    def test_revision_and_append_only_history_are_consistent(self):
        for cardfile in sorted((DOCS / 'cards').glob('KBN-????.json')):
            card = json.loads(cardfile.read_text(encoding='utf-8'))
            events = [json.loads(line) for line in
                (DOCS / 'history' / f'{card["id"]}.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual(events[-1]['revision'], card['revision'])
            self.assertTrue(any(event['action'] == 'documentation-audit' and
                                'M439:' in event['detail'] for event in events))
            self.assertEqual(events[-1]['afterSha256'], hashlib.sha256(
                json.dumps(card, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest())

    def test_current_docs_never_confuse_studio_with_static_code(self):
        report = (DOCS / 'STATUS_2026-11-22_M439.md').read_text('utf-8')
        self.assertIn('`publishAllowed=false`', report)
        self.assertIn('`cooking_pot_socket`', report)
        self.assertIn('Studio Play', report)
        for card in KanbanStore(ROOT).list_cards()['cards']:
            self.assertIn(card['id'], report)
        self.assertIn('все 17', report)

    def test_normal_verify_validator_rejects_out_of_band_doc_change(self):
        from validators.kanban_integrity import check_kanban_integrity
        errors = []
        check_kanban_integrity(ROOT, errors.append)
        self.assertEqual(errors, [])
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root/'system/control-center').mkdir(parents=True)
            shutil.copy2(ROOT/'system/control-center/kanban_store.py',
                         root/'system/control-center/kanban_store.py')
            (root/'docs/kanban/cards').mkdir(parents=True)
            (root/'docs/kanban/specs').mkdir(parents=True)
            (root/'docs/kanban/history').mkdir(parents=True)
            source_card = DOCS/'cards/KBN-0001.json'
            source_spec = DOCS/'specs/KBN-0001.md'
            shutil.copy2(source_card, root/'docs/kanban/cards/KBN-0001.json')
            dst = root/'docs/kanban/specs/KBN-0001.md'
            shutil.copy2(source_spec, dst)
            dst.write_text(dst.read_text('utf-8')+'\nUnexpected edit\n', encoding='utf-8')
            errors = []
            check_kanban_integrity(root, errors.append)
            self.assertEqual(len(errors), 1)
            self.assertIn('documentation differs', errors[0])

    def test_navigation_explains_documentation_authority(self):
        readme = (DOCS / 'README.md').read_text('utf-8')
        self.assertIn('STATUS_2026-11-22_M439.md', readme)
        self.assertIn('M439', (ROOT/'docs/workflows/DOCUMENTATION_RULES_RU.md').read_text('utf-8'))
        self.assertIn('specSha256', (ROOT/'docs/workflows/DOCUMENTATION_RULES_RU.md').read_text('utf-8'))
        ui = (ROOT/'system/control-center/static/kanban.js').read_text('utf-8')
        self.assertNotIn('все пункты изначально PROPOSED', ui)
        self.assertIn('карточек', ui)


if __name__ == '__main__':
    unittest.main()
