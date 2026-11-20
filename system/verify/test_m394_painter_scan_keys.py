"""M394: verified LandscapePainter keys can reach Studio Sync, never Repair."""
from __future__ import annotations

import json
import socket
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock
from urllib.request import Request, urlopen
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services import studio_place_registry_bridge as transport


class PainterScanKeyBridgeTests(unittest.TestCase):
    CATALOG = {'domain': 'location_assets', 'digest': 'test-digest', 'items': []}
    TOKEN = 'a' * 32

    def test_external_keys_invalid_for_repair_and_malformed_for_every_action(self):
        for phase, keys in (
            ('repair', ['x1']), ('repair', ['p1', 'x2']),
            ('sync', []), ('sync', ['x0']), ('sync', ['x01']),
            ('sync', ['x100000']), ('sync', ['x1', 'x1']),
            ('sync', ['x1', 'p1', 'p1']), ('sync', ['x1', 2]), ('sync', ['x1', []]),
            ('sync', ['x_2']), ('select', ['x-1']),
        ):
            with self.subTest(phase=phase, keys=keys), self.assertRaisesRegex(
                    ValueError, 'select explicit scanned placement keys'):
                transport.run_place_registry_bridge(
                    catalog=self.CATALOG, phase=phase, scan_token=self.TOKEN, keys=keys)

    def test_scan_token_is_required_for_external_keys(self):
        with self.assertRaisesRegex(ValueError, 'Scan the Place'):
            transport.run_place_registry_bridge(
                catalog=self.CATALOG, phase='sync', scan_token='', keys=['x1'])

    def test_sync_mixed_keys_roundtrip_and_selection_of_external_key(self):
        for phase, keys in (('sync', ['p1', 'x1', 'x2']), ('select', ['x3'])):
            with self.subTest(phase=phase):
                with socket.socket() as sock:
                    sock.bind(('127.0.0.1', 0))
                    port = sock.getsockname()[1]
                result = {}

                def studio_bridge():
                    try:
                        result['report'] = transport.run_place_registry_bridge(
                            catalog=self.CATALOG, phase=phase,
                            scan_token=self.TOKEN, keys=keys, timeout_seconds=5)
                    except BaseException as err:
                        result['error'] = err

                with mock.patch.object(transport, 'PORT', port):
                    runner = threading.Thread(target=studio_bridge, daemon=True)
                    runner.start()
                    command = None
                    for _ in range(250):
                        try:
                            with urlopen(Request(
                                    f'http://127.0.0.1:{port}/command',
                                    headers={'X-Game1-Token': transport.TOKEN}), timeout=0.3) as response:
                                command = json.load(response)
                            break
                        except (URLError, TimeoutError, OSError):
                            time.sleep(.01)
                    self.assertIsNotNone(command, 'Studio Bridge did not expose command')
                    self.assertEqual(command['keys'], keys)
                    self.assertEqual(command['phase'], phase)
                    confirmation = {
                        'project': transport.PROJECT,
                        'command': 'location-place-registry',
                        'schemaVersion': 1,
                        'operationId': command['operationId'],
                        'catalogDigest': self.CATALOG['digest'],
                        'phase': phase,
                        'result': {'changed': len(keys)},
                    }
                    with urlopen(Request(
                            f'http://127.0.0.1:{port}/place-registry-result',
                            data=json.dumps(confirmation).encode(), method='POST',
                            headers={'X-Game1-Token': transport.TOKEN}), timeout=1) as response:
                        self.assertTrue(json.load(response)['ok'])
                    runner.join(5)
                self.assertNotIn('error', result)
                self.assertEqual(result['report']['result']['changed'], len(keys))

    def test_studio_rechecks_keys_against_scanned_session(self):
        studio = (ROOT / 'system/studio-plugin/modules/StudioPlaceRegistryCommands.luau').read_text('utf-8')
        self.assertIn('not session.refs[key]', studio)
        self.assertIn('if not Inventory.Validate(ref) then', studio)
        self.assertIn('if phase=="repair" then', studio)


if __name__ == '__main__':
    unittest.main()
