"""M339: functional Kanban tests. No Studio/SQLite/Roblox side effects."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / 'system' / 'control-center'
sys.path.insert(0, str(HOST))

from kanban_store import KanbanError, KanbanStore
from api.read_dispatch import dispatch as dispatch_read
from api.write_dispatch import dispatch_post


class TestDevelopmentKanbanM339(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        card_dir = self.root / 'docs/kanban/cards'
        spec_dir = self.root / 'docs/kanban/specs'
        card_dir.mkdir(parents=True)
        spec_dir.mkdir(parents=True)
        self.spec = '# KBN-0001\nInitial contract\n'
        (spec_dir / 'KBN-0001.md').write_text(self.spec, encoding='utf-8')
        self.card = {
            'schemaVersion': 1, 'id': 'KBN-0001', 'title': 'Test task',
            'domain': 'Tooling', 'status': 'PROPOSED', 'priority': 'P0', 'owner': 'Codex',
            'specPath': 'docs/kanban/specs/KBN-0001.md', 'specSha256': hashlib.sha256(self.spec.encode()).hexdigest(),
            'revision': 1, 'dependsOn': [],
            'tasks': [{'id': 'KBN-0001-T01', 'title': 'Work', 'done': False}],
            'acceptance': [{'id': 'KBN-0001-A01', 'title': 'Device test', 'status': 'NOT_RUN', 'evidence': ''}],
        }
        self.path = card_dir / 'KBN-0001.json'
        self.path.write_text(json.dumps(self.card, ensure_ascii=False), encoding='utf-8')
        self.store = KanbanStore(self.root)

    def apply(self, action, **kwargs):
        revision = self.store.detail('KBN-0001')['card']['revision']
        return self.store.update('KBN-0001', {'action': action, 'expectedRevision': revision, **kwargs})

    def test_seeded_project_cards_have_documents_and_hashes(self):
        production = KanbanStore(ROOT)
        result = production.list_cards()['cards']
        self.assertGreaterEqual(len(result), 13)
        self.assertTrue({f'KBN-{i:04d}' for i in range(1, 14)}.issubset({c['id'] for c in result}))
        # Existing cards may legitimately change status or new cards may be added via UI.
        self.assertIn(production.detail('KBN-0013')['card']['status'],
                      ('READY', 'IN_PROGRESS', 'CODE_COMPLETE', 'VALIDATING', 'DONE', 'BLOCKED', 'ON_HOLD'))
        self.assertIn('FULL', production.detail('KBN-0007')['spec'])
        self.assertIn('KBN-0012', production.export()['markdown'])

    def test_real_estate_collision_blueprint_contract_is_registered(self):
        production = KanbanStore(ROOT)
        detail = production.detail('KBN-0013')
        card, spec = detail['card'], detail['spec']
        self.assertEqual(card['priority'], 'P0')
        self.assertGreaterEqual(len(card['tasks']), 10)
        self.assertTrue(all(type(task['done']) is bool for task in card['tasks']))
        self.assertTrue(all(test['status'] in ('NOT_RUN', 'PASS', 'FAIL', 'BLOCKED')
                            for test in card['acceptance']))
        for mandatory in ('StudioRealEstateHouseFrame', 'legacy-model-pivot',
                          'Col_meshRig', 'PreciseConvexDecomposition', 'Rollback', 'Location Assets'):
            self.assertIn(mandatory.lower(), spec.lower())
        self.assertIn('KBN-0013', production.export()['markdown'])

    def test_optimistic_revision_and_backup_and_history(self):
        self.apply('task', itemId='KBN-0001-T01', done=True)
        self.assertTrue(self.store.detail('KBN-0001')['card']['tasks'][0]['done'])
        self.assertEqual(self.store.detail('KBN-0001')['card']['revision'], 2)
        with self.assertRaises(KanbanError) as conflict:
            self.store.update('KBN-0001', {'expectedRevision': 1, 'action': 'status', 'status': 'READY'})
        self.assertEqual(conflict.exception.status, 409)
        backup = list((self.root / '.control-center/backups/kanban/KBN-0001').glob('*/KBN-0001.json'))
        self.assertEqual(len(backup), 1)
        self.assertEqual(len(self.store.history_for('KBN-0001')['events']), 1)

    def test_done_requires_tasks_and_concrete_test_evidence(self):
        with self.assertRaisesRegex(KanbanError, 'DONE requires'):
            self.apply('status', status='DONE')
        self.apply('task', itemId='KBN-0001-T01', done=True)
        with self.assertRaisesRegex(KanbanError, 'PASS requires'):
            self.apply('acceptance', itemId='KBN-0001-A01', status='PASS', evidence='')
        with self.assertRaisesRegex(KanbanError, 'DONE requires'):
            self.apply('status', status='DONE')
        self.apply('acceptance', itemId='KBN-0001-A01', status='PASS', evidence='Tested in Studio on 2026-11-13')
        self.apply('status', status='DONE')
        self.assertEqual(self.store.detail('KBN-0001')['card']['status'], 'DONE')

    def test_documentation_change_reason_and_approved_contract_lock(self):
        self.apply('status', status='READY')
        with self.assertRaisesRegex(KanbanError, 'requires a reason'):
            self.apply('spec', spec='# New', reason='')
        with self.assertRaises(KanbanError) as locked:
            self.apply('spec', spec='# New', reason='Architectural change')
        self.assertEqual(locked.exception.status, 409)
        self.apply('spec', spec='# New', reason='Owner approved new contract', confirmPolicyChange=True)
        self.assertEqual(self.store.detail('KBN-0001')['spec'], '# New')
        self.assertEqual(len(self.store.history_for('KBN-0001')['events']), 2)

    def test_detect_out_of_band_git_edits_and_path_injection(self):
        (self.root / 'docs/kanban/specs/KBN-0001.md').write_text('Manual git edit', encoding='utf-8')
        with self.assertRaises(KanbanError) as conflict:
            self.store.detail('KBN-0001')
        self.assertEqual(conflict.exception.status, 409)
        for illegal in ('../../README', 'KBN-0001/../../abc', 'KBN-0001%2f..', 'KBN-0003'):
            with self.assertRaises(KanbanError):
                self.store.detail(illegal)
        self.assertFalse((self.root / 'README').exists())

    def test_http_adapters_do_not_affect_other_routes(self):
        read_sources={'kanban': self.store}
        write_sources={'kanban': self.store}
        status, data = dispatch_read(urlsplit('/api/kanban/KBN-0001'), read_sources, lambda: {})
        self.assertEqual((status, data['card']['id']), (200, 'KBN-0001'))
        status, data = dispatch_post('/api/kanban/KBN-0001', lambda: {'expectedRevision': 1, 'action': 'task', 'itemId': 'KBN-0001-T01', 'done': True}, write_sources)
        self.assertEqual((status, data['card']['revision']), (200, 2))
        status, data = dispatch_post('/api/kanban/KBN-0001', lambda: {'expectedRevision': 1, 'action': 'task', 'itemId': 'KBN-0001-T01', 'done': False}, write_sources)
        self.assertEqual(status, 409)
        status, data = dispatch_read(urlsplit('/api/kanban/export'), read_sources, lambda: {})
        self.assertEqual(status, 200)
        self.assertIn('KBN-0001', data['markdown'])

    def test_create_card_and_add_checklist_items(self):
        created = self.store.create({'title': 'Independent test feature', 'domain': 'Assets', 'priority': 'P2', 'owner': 'Codex'})
        self.assertEqual(created['card']['id'], 'KBN-0002')
        self.assertEqual(created['card']['status'], 'PROPOSED')
        self.assertTrue((self.root / 'docs/kanban/specs/KBN-0002.md').exists())
        data = self.store.update('KBN-0002', {'expectedRevision': 1, 'action': 'task-add', 'title': 'Make a reproducible build'})
        self.assertEqual(len(data['card']['tasks']), 2)
        data = self.store.update('KBN-0002', {'expectedRevision': 2, 'action': 'acceptance-add', 'title': 'Run real-device smoke test'})
        self.assertEqual(len(data['card']['acceptance']), 2)
        data = self.store.update('KBN-0002', {'expectedRevision': 3, 'action': 'item-title', 'itemId': 'KBN-0002-T02', 'title': 'Record a reproducible build'})
        self.assertEqual(data['card']['tasks'][1]['title'], 'Record a reproducible build')

    def test_dependency_gate_for_completion(self):
        other = self.store.create({'title': 'Dependent task'})['card']['id']
        card_file = self.root / f'docs/kanban/cards/{other}.json'
        data = json.loads(card_file.read_text(encoding='utf-8'))
        data['dependsOn'] = ['KBN-0001']
        card_file.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        current = self.store.detail(other)['card']
        self.store.update(other, {'expectedRevision': current['revision'], 'action':'task', 'itemId':f'{other}-T01', 'done':True})
        current = self.store.detail(other)['card']
        self.store.update(other, {'expectedRevision': current['revision'], 'action':'acceptance', 'itemId':f'{other}-A01', 'status':'PASS', 'evidence':'Verification log'})
        current = self.store.detail(other)['card']
        with self.assertRaisesRegex(KanbanError, 'dependencies'):
            self.store.update(other, {'expectedRevision': current['revision'], 'action':'status', 'status':'DONE'})

    def test_closed_card_cannot_be_modified_without_reopen(self):
        self.apply('task', itemId='KBN-0001-T01', done=True)
        self.apply('acceptance', itemId='KBN-0001-A01', status='PASS', evidence='Android smoke test record')
        self.apply('status', status='DONE')
        for action in ({'action': 'task', 'itemId': 'KBN-0001-T01', 'done': False},
                       {'action': 'acceptance-add', 'title': 'New condition'},
                       {'action': 'spec', 'spec': '# Updated', 'reason': 'Owner approved change', 'confirmPolicyChange': True}):
            with self.assertRaises(KanbanError) as conflict:
                self.store.update('KBN-0001', {'expectedRevision': 4, **action})
            self.assertEqual(conflict.exception.status, 409)

    def test_reject_invalid_create_and_invalid_checklist_state(self):
        for invalid in ({'title':'x'}, {'title':'Valid new feature','priority':'F'},
                        {'title':'Valid new feature','domain':'../../escape'}):
            with self.assertRaises(KanbanError):
                self.store.create(invalid)
        with self.assertRaises(KanbanError):
            self.apply('acceptance', itemId='KBN-0001-A01', status=[], evidence='any')
        self.assertEqual(self.store.list_cards()['cards'][0]['revision'], 1)

    def test_ui_integration(self):
        base = HOST / 'static'
        html = (base / 'index.html').read_text(encoding='utf-8')
        js = (base / 'character-assets.js').read_text(encoding='utf-8')
        self.assertIn('id="nav-kanban"', html)
        self.assertIn('id="kanban-view"', html)
        self.assertIn('kanban.js?v=339', html)
        self.assertIn("view!=='kanban'", js)
        self.assertIn("game1KanbanLoad", js)
        self.assertTrue((base / 'kanban.js').is_file())
        self.assertTrue((base / 'kanban.css').is_file())


if __name__ == '__main__':
    unittest.main()
