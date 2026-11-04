"""M225: Place must prove BasePart anchoring and reject pre-M225 Studio plugins."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import threading
import time
from unittest import TestCase
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system' / 'control-center'))
from services.studio_house_placement_bridge import preview_house_placement
from studio_bridge import PORT, TOKEN, StudioBridgeError


def dummy_binding(anchored: bool) -> dict:
    return {
        'houseSlug': 'house_a', 'plotIndex': 1, 'revision': 2,
        'anchored': anchored, 'scale': 1,
        'localCFrame': [0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1],
    }


class VerifiedPreviewBridge(TestCase):
    def dispatch_fake_studio(self, result_fields: dict, expected_anchored: bool,
                             *, stale: bool = False):
        observed = []
        errors = []
        def simulated_studio():
            try:
                base = f'http://127.0.0.1:{PORT}'
                for _ in range(100):
                    try:
                        with urlopen(Request(base + '/command', headers={
                            'X-Game1-Token': TOKEN}), timeout=.5) as response:
                            cmd = json.load(response)
                        break
                    except OSError:
                        time.sleep(.025)
                else:
                    raise AssertionError('Bridge never served the preview command')
                observed.append(cmd)
                self.assertEqual(cmd['command'], 'house-placement-preview-v2')
                self.assertEqual(cmd['schemaVersion'], 2)
                self.assertEqual(cmd['action'], 'place')
                self.assertIs(cmd['placement']['anchored'], expected_anchored)
                response_fields = {
                    **cmd, 'status': 'placed', 'anchored': expected_anchored,
                    'anchoredPartsVerified': 3, **result_fields,
                }
                if stale:
                    response_fields['command'] = 'house-placement-preview'
                    response_fields['schemaVersion'] = 1
                data = json.dumps(response_fields).encode('utf-8')
                try:
                    with urlopen(Request(base + '/house-placement-result', data=data,
                        headers={'X-Game1-Token': TOKEN, 'Content-Type': 'application/json'},
                        method='POST'), timeout=2) as response:
                        observed.append(response.status)
                except HTTPError as exc:
                    observed.append(exc.code)
            except Exception as exc:
                errors.append(exc)
        worker = threading.Thread(target=simulated_studio, daemon=True)
        worker.start()
        try:
            if stale:
                with self.assertRaises(StudioBridgeError):
                    preview_house_placement('house_a', 1, 'place',
                        dummy_binding(expected_anchored), timeout_seconds=3)
            elif (result_fields.get('anchored', expected_anchored) is not expected_anchored
                  or result_fields.get('anchoredPartsVerified', 3) < 1):
                with self.assertRaisesRegex(StudioBridgeError, 'did not verify'):
                    preview_house_placement('house_a', 1, 'place',
                        dummy_binding(expected_anchored), timeout_seconds=3)
            else:
                response = preview_house_placement('house_a', 1, 'place',
                    dummy_binding(expected_anchored), timeout_seconds=3)
                self.assertIs(response['anchored'], expected_anchored)
                self.assertEqual(response['anchoredPartsVerified'], 3)
        finally:
            worker.join(timeout=4)
        self.assertEqual(errors, [])
        self.assertEqual(observed[1], 400 if stale else 200)

    def test_free_is_explicitly_sent_and_verified(self):
        self.dispatch_fake_studio({}, False)

    def test_anchored_is_explicitly_sent_and_verified(self):
        self.dispatch_fake_studio({}, True)

    def test_mismatch_from_studio_is_not_success(self):
        self.dispatch_fake_studio({'anchored': True}, False)

    def test_zero_parts_is_not_success(self):
        self.dispatch_fake_studio({'anchoredPartsVerified': 0}, False)

    def test_stale_plugin_command_identity_rejected(self):
        self.dispatch_fake_studio({}, False, stale=True)

    def test_non_boolean_binding_is_rejected_before_studio(self):
        value = dummy_binding(False)
        value['anchored'] = 'false'
        with self.assertRaisesRegex(ValueError, 'anchored boolean'):
            preview_house_placement('house_a', 1, 'place', value)

    def test_shared_plugin_contract_has_no_legacy_preview_dispatch(self):
        router = (ROOT / 'system/studio-plugin/Game1Bridge.server.luau').read_text()
        studio = (ROOT / 'system/studio-plugin/modules/StudioHousePlacementPreview.luau').read_text()
        self.assertIn('data.command == "house-placement-preview-v2"', router)
        self.assertNotIn('data.command == "house-placement-preview"', router)
        self.assertIn('command.schemaVersion ~= 2', studio)
        self.assertIn('setAndVerifyAnchored(clone, binding.anchored)', studio)
        self.assertIn('verifiedParts = setAndVerifyAnchored(clone, binding.anchored)', studio)
        self.assertIn('anchoredPartsVerified = verifiedParts', studio)
        self.assertIn('clone.Parent = folder', studio)
        self.assertLess(studio.index('clone.Parent = folder'),
                        studio.index('verifiedParts = setAndVerifyAnchored'))

    def test_atlas_panel_has_own_outer_and_inner_spacing(self):
        css = (ROOT / 'system/control-center/static/atlas-library.css').read_text()
        self.assertIn('.atlas-library-panel{min-width:0;margin-top:14px;padding:22px 24px}', css)
        self.assertIn('@media(max-width:700px){.atlas-library-panel{padding:15px 12px}}', css)
