"""M118: Location Assets Studio sync is an explicit, read-only DecoManager refresh."""
from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import socket
import sys
import threading
import time
from unittest import TestCase, mock
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from api.write_world import route
from services import studio_deco_bridge as bridge


def unused_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def studio_request(port, path, *, method='GET', data=None, token=bridge.TOKEN):
    encoded = json.dumps(data).encode('utf-8') if data is not None else None
    headers = {'X-Game1-Token': token}
    if encoded is not None:
        headers['Content-Type'] = 'application/json'
    with urlopen(Request(f'http://127.0.0.1:{port}{path}',
                         data=encoded, headers=headers, method=method), timeout=3) as response:
        return json.load(response)


class LocationAssetsSyncM118(TestCase):
    def test_route_executes_injected_bridge_without_persistence(self):
        calls = []
        deps = defaultdict(lambda: object())
        deps['sync_location_assets_to_studio'] = lambda: (
            calls.append('refresh'), {'models': 2, 'parts': 3, 'registryItems': 4})[1]
        status, payload = route('/api/location-assets/studio-sync', lambda: {}, deps)
        self.assertEqual(status, 200)
        self.assertEqual(payload['studio']['parts'], 3)
        self.assertEqual(calls, ['refresh'])
        deps['sync_location_assets_to_studio'] = lambda: (_ for _ in ()).throw(
            RuntimeError('studio offline'))
        status, payload = route('/api/location-assets/studio-sync', lambda: {}, deps)
        self.assertEqual(status, 400)
        self.assertIn('studio offline', payload['error'])

    def _start_bridge(self, port, **kwargs):
        outcome = {}
        def worker():
            try:
                outcome['value'] = bridge.run_deco_refresh_bridge(**kwargs)
            except Exception as error:
                outcome['error'] = error
        patcher = mock.patch.object(bridge, 'PORT', port)
        patcher.start()
        self.addCleanup(patcher.stop)
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        return thread, outcome

    def _claim(self, port):
        for _ in range(100):
            try:
                return studio_request(port, '/command')
            except (URLError, OSError):
                time.sleep(.02)
        self.fail('bridge did not start')

    def test_real_studio_bridge_roundtrip_and_identity_guard(self):
        port = unused_port()
        thread, outcome = self._start_bridge(port, timeout_seconds=5.0)
        command = self._claim(port)
        self.assertEqual(command['command'], 'deco-refresh')
        self.assertEqual(command['schemaVersion'], 1)
        self.assertTrue(command['operationId'])
        with self.assertRaises(HTTPError) as unauthorized:
            studio_request(port, '/command', token='wrong')
        self.assertEqual(unauthorized.exception.code, 403)
        with self.assertRaises(HTTPError) as wrong_identity:
            studio_request(port, '/deco-refresh-result', method='POST', data={
                **command, 'operationId': 'not-this-operation',
                'models': 9, 'parts': 9, 'registryItems': 9,
            })
        self.assertEqual(wrong_identity.exception.code, 400)
        studio_request(port, '/deco-refresh-result', method='POST', data={
            **command, 'models': 2, 'parts': 5, 'registryItems': 18,
        })
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(outcome.get('value'), {'models': 2, 'parts': 5, 'registryItems': 18})

    def test_studio_reports_failure_and_browser_does_not_claim_success(self):
        port = unused_port()
        thread, outcome = self._start_bridge(port, timeout_seconds=5.0)
        command = self._claim(port)
        studio_request(port, '/deco-refresh-result', method='POST', data={
            **command, 'error': 'registry HTTP 500',
        })
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertIn('registry HTTP 500', str(outcome.get('error')))
        self.assertNotIn('value', outcome)

    def test_no_studio_returns_error_not_success(self):
        port = unused_port()
        thread, outcome = self._start_bridge(port, timeout_seconds=1)
        thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertIn('Studio did not complete', str(outcome.get('error')))

    def test_no_publish_or_model_load_in_studio_sync_and_ui_wiring(self):
        def source(path):
            return (ROOT / path).read_text(encoding='utf-8')
        html = source('system/control-center/static/index.html')
        js = source('system/control-center/static/deco-assets.js')
        studio = source('system/studio-plugin/Game1Bridge.server.luau')
        commands = source('system/studio-plugin/modules/StudioDecoSyncCommands.luau')
        sync = source('system/studio-plugin/modules/DecoManager.luau')
        project = json.loads(source('system/studio-plugin/plugin.project.json'))
        self.assertIn('id="sync-location-assets"', html)
        self.assertIn('decoAssetSyncStudio', js)
        self.assertIn("'/api/location-assets/studio-sync'", js)
        self.assertIn('data.command == "deco-refresh"', studio)
        self.assertIn('config.decoManager:refreshRegistry()', commands)
        self.assertIn('DecoPlacedAssetSync.RefreshTextures(', sync)
        self.assertIn('return { models = syncResult.models', sync)
        self.assertEqual(project['tree']['modules']['StudioDecoSyncCommands']['$path'],
                         'modules/StudioDecoSyncCommands.luau')
        self.assertNotIn('LoadAssetAsync', commands)
        self.assertNotIn('game:GetService("ServerStorage")', commands)
