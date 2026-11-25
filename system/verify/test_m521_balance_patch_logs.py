import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from api import balance as api
from services import balance_patch_logs as logs


class PatchLogs(unittest.TestCase):
    def test_read_only_endpoint_and_seed(self):
        status, data = api.read('/api/balance/logs', {})
        self.assertEqual(status, 200)
        self.assertEqual(data['entries'][0], {'patch': 520, 'message': 'Увеличили всем монстрам хп на 20%'})
        self.assertIsNone(api.write('/api/balance/logs', lambda: self.fail('must not read body'), {}))

    def test_future_entries_and_invalid_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'logs.json'
            with patch.object(logs, 'SOURCE', source):
                rows = [{'patch': 520, 'message': 'HP +20%'}, {'patch': 522, 'message': 'XP +10%'}]
                def read(entries):
                    source.write_text(json.dumps({'schemaVersion': 1, 'entries': entries}), encoding='utf-8')
                    return api.read('/api/balance/logs', {})
                self.assertEqual(read(rows), (200, {'schemaVersion': 1, 'entries': rows}))
                for invalid in ([rows[0], rows[0]], list(reversed(rows)), [{'patch': 522, 'message': 'one\ntwo'}]):
                    self.assertEqual(read(invalid)[0], 500)
                source.unlink()
                self.assertEqual(api.read('/api/balance/logs', {})[0], 500)
