"""M251: Alpha-only scan response must survive the real Studio HTTP transport.

An Alpha flag is a per-Location Asset appearance setting, not a new Model/Atlas ID.
"""
from __future__ import annotations

import json
from pathlib import Path
import socket
import sys
import threading
import time
import unittest
from unittest import mock
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services import studio_deco_bridge as bridge


class AlphaScanTransportM251(unittest.TestCase):
    def test_studio_command_whitelist_transports_alpha_pending(self):
        source = (ROOT / 'system/studio-plugin/modules/StudioDecoSyncCommands.luau').read_text(
            encoding='utf-8'
        )
        scan_fields = source.split('if command.phase=="scan" then {', 1)[1].split(
            '} elseif command.phase=="select"', 1
        )[0]
        self.assertIn('"alphaPending"', scan_fields)

    def make_report(self, *, alpha_current=False, enabled=True):
        part = {
            'key': 'p1', 'name': 'bush_01', 'path': 'Workspace.Trees.bush_01.bush_01',
            'modelName': 'bush_01', 'modelPath': 'Workspace.Trees.bush_01',
            'meshId': '444', 'textureId': '999', 'colorMapId': '999',
            'instanceId': 'instance-1', 'historicalModelId': '',
            'isCollider': False, 'managed': True, 'meshCurrent': True,
            'textureCurrent': True, 'needsMesh': False, 'needsTexture': False,
            'hasSurface': True, 'textureApplicable': True, 'attachable': False,
            'needsAlpha': not alpha_current, 'alphaCurrent': alpha_current,
            'alphaEnabled': enabled,
        }
        return {
            'project': bridge.PROJECT, 'command': 'deco-refresh',
            'schemaVersion': 9, 'targetSlug': 'bush_01',
            'bindingRevision': 3, 'phase': 'scan',
            'scanToken': 'a' * 32,
            'mode': 'alpha' if not alpha_current else 'current',
            'foundMeshParts': 1, 'managedMeshParts': 1, 'unmanagedMeshParts': 0,
            'managedModels': 1, 'texturePending': 0, 'meshPending': 0,
            'geometryPending': 0, 'alphaPending': 0 if alpha_current else 1,
            'inventory': [{'modelAssetId': '12345', 'meshes': [{'meshId': '444', 'count': 1}]}],
            'expectedMeshIds': ['444'], 'parts': [part],
        }

    def exchange(self, report):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        outcome = {}

        def worker():
            try:
                outcome['result'] = bridge.run_deco_refresh_bridge(
                    timeout_seconds=4, slug='bush_01', binding_revision=3,
                    model_asset_id='12345', atlas_asset_id='999', phase='scan',
                    model_history=['12345'])
            except Exception as exc:
                outcome['error'] = exc

        with mock.patch.object(bridge, 'PORT', port):
            thread = threading.Thread(target=worker, daemon=True)
            thread.start()
            command = None
            for _ in range(150):
                try:
                    with urlopen(Request(f'http://127.0.0.1:{port}/command',
                                         headers={'X-Game1-Token': bridge.TOKEN}),
                                 timeout=1) as response:
                        command = json.load(response)
                    break
                except (URLError, OSError):
                    time.sleep(.01)
            self.assertIsNotNone(command)
            with urlopen(Request(f'http://127.0.0.1:{port}/deco-refresh-result',
                                 data=json.dumps(dict(report, operationId=command['operationId'])).encode(),
                                 method='POST', headers={
                                     'X-Game1-Token': bridge.TOKEN,
                                     'Content-Type': 'application/json'}), timeout=2) as response:
                self.assertTrue(json.load(response)['ok'])
            thread.join(5)
        self.assertFalse(thread.is_alive())
        return outcome

    def test_alpha_only_scan_is_accepted_and_pending_count_is_preserved(self):
        result = self.exchange(self.make_report())
        self.assertNotIn('error', result, result)
        scan = result['result']
        self.assertEqual(scan['mode'], 'alpha')
        self.assertEqual(scan['alphaPending'], 1)
        self.assertEqual(scan['texturePending'], 0)
        self.assertTrue(scan['parts'][0]['needsAlpha'])
        self.assertTrue(scan['parts'][0]['alphaEnabled'])

    def test_turning_alpha_off_also_uses_alpha_only_mode(self):
        result = self.exchange(self.make_report(enabled=False))
        self.assertNotIn('error', result, result)
        self.assertEqual(result['result']['mode'], 'alpha')
        self.assertEqual(result['result']['alphaPending'], 1)
        self.assertFalse(result['result']['parts'][0]['alphaEnabled'])

    def test_alpha_current_scan_has_no_pending_changes(self):
        result = self.exchange(self.make_report(alpha_current=True))
        self.assertNotIn('error', result, result)
        self.assertEqual(result['result']['mode'], 'current')
        self.assertEqual(result['result']['alphaPending'], 0)

    def test_mismatched_alpha_counts_are_rejected_not_silently_ignored(self):
        report = self.make_report()
        report['alphaPending'] = 0
        result = self.exchange(report)
        self.assertIsInstance(result.get('error'), bridge.StudioBridgeError)
        self.assertIn('alpha count mismatch', str(result['error']))

    def test_non_boolean_alpha_flags_are_rejected(self):
        report = self.make_report()
        report['parts'][0]['needsAlpha'] = 'true'
        result = self.exchange(report)
        self.assertIsInstance(result.get('error'), bridge.StudioBridgeError)
        self.assertIn('Alpha flag', str(result['error']))


if __name__ == '__main__':
    unittest.main()
