"""M227 — one house/50 plot bulk preview, scoped clearing and bridge contracts."""
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, mock
import json
import sys
import threading
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system' / 'control-center'))
from api import real_estate as api
from services import studio_house_placement_bridge as bridge
from studio_bridge import PORT, TOKEN, StudioBridgeError


def binding(house='house_a', plot=1, anchored=True):
    return {'houseSlug': house, 'plotIndex': plot, 'revision': 3, 'scale': 1.25,
            'anchored': anchored,
            'localCFrame': [3, 2, 1, 1, 0, 0, 0, 1, 0, 0, 0, 1]}


class BulkPreviewRoute(TestCase):
    def setUp(self):
        self.records = [binding('house_b', 1), binding('house_a', 3, False), binding('house_a', 1)]
        self.bulk = mock.Mock(return_value={'status': 'placed_all', 'changed': 2})
        self.deps = {'real_estate': SimpleNamespace(get=lambda s: {'slug': s} if s in ('house_a', 'house_b') else None),
                     'real_estate_placements': SimpleNamespace(snapshot=lambda: {'items': self.records}),
                     'bulk_house_placements': self.bulk}

    def test_place_all_uses_only_selected_house_and_server_bindings(self):
        payload = {'action': 'place_all', 'houseSlug': 'house_a',
                   'targets': [binding('house_b', 12)], 'localCFrame': [900] * 12}
        status, reply = api.write('/api/real-estate/placements/bulk', lambda: payload, self.deps)
        self.assertEqual(status, 200)
        self.assertEqual(reply['studio']['changed'], 2)
        args = self.bulk.call_args.args
        self.assertEqual(args[0:2], ('house_a', 'place_all'))
        self.assertEqual(args[2], [self.records[1], self.records[2]])
        self.assertEqual(args[2][0]['localCFrame'], binding('house_a', 3)['localCFrame'])

    def test_clear_all_requires_no_current_binding_or_selected_house(self):
        self.records = []
        status, _ = api.write('/api/real-estate/placements/bulk', lambda: {
            'action': 'clear_all', 'houseSlug': 'no_such_house', 'targets': [binding()]}, self.deps)
        self.assertEqual(status, 200)
        self.bulk.assert_called_once_with(None, 'clear_all')

    def test_invalid_or_unbound_place_rejected_without_studio(self):
        for request in [{'action': 'place_all', 'houseSlug': 'unknown'},
                        {'action': 'whatever'}, {'action': 'place_all', 'houseSlug': 'house_b'}]:
            self.bulk.reset_mock()
            if request.get('houseSlug') == 'house_b':
                self.records = []
            status, reply = api.write('/api/real-estate/placements/bulk', lambda r=request: r, self.deps)
            self.assertEqual(status, 400)
            self.assertIn('error', reply)
            self.bulk.assert_not_called()


class BulkPreviewBridge(TestCase):
    def test_rejects_bad_targets_before_sending_studio_command(self):
        with mock.patch.object(bridge, '_request_house_placement') as request:
            invalids = [
                [binding('house_a', 1), binding('house_a', 1)],
                [binding('house_a', 1, 'false')],
                [binding('wrong', 1)],
                [binding('house_a', 0)],
                [binding('house_a', 1, True) | {'localCFrame': []}],
                [],
            ]
            for targets in invalids:
                with self.subTest(targets=targets), self.assertRaises(ValueError):
                    bridge.bulk_house_placements('house_a', 'place_all', targets)
            request.assert_not_called()

    def test_requires_full_verified_place_result(self):
        with mock.patch.object(bridge, '_request_house_placement') as request:
            request.return_value = {'status': 'placed_all', 'changed': 1,
                                    'anchoredPartsVerified': 0}
            with self.assertRaisesRegex(StudioBridgeError, 'did not verify'):
                bridge.bulk_house_placements('house_a', 'place_all', [binding()])
            request.return_value['anchoredPartsVerified'] = 1
            self.assertEqual(bridge.bulk_house_placements('house_a', 'place_all', [binding()])['changed'], 1)
            args, kwargs = request.call_args
            self.assertEqual(args, ('house_a', 0))
            self.assertEqual(kwargs['action'], 'place_all')
            self.assertEqual(kwargs['targets'][0]['anchored'], True)

    def test_clear_all_rejects_unverified_result(self):
        with mock.patch.object(bridge, '_request_house_placement') as request:
            request.return_value = {'status': 'already_clear', 'changed': 0}
            with self.assertRaises(StudioBridgeError):
                bridge.bulk_house_placements(None, 'clear_all')
            request.return_value = {'status': 'cleared_all', 'changed': 0}
            self.assertEqual(bridge.bulk_house_placements(None, 'clear_all')['changed'], 0)
            self.assertEqual(request.call_args.args, ('*', 0))
            self.assertEqual(request.call_args.kwargs['targets'], [])

    def test_authenticated_studio_roundtrip_one_command(self):
        received, faults = [], []

        def simulated_studio():
            try:
                base = f'http://127.0.0.1:{PORT}'
                for _ in range(100):
                    try:
                        with urlopen(Request(base + '/command', headers={'X-Game1-Token': TOKEN}),
                                     timeout=.5) as response:
                            command = json.load(response)
                        break
                    except OSError:
                        time.sleep(.025)
                else:
                    raise AssertionError('Bridge never served command')
                received.append(command)
                reply = dict(command, status='placed_all', changed=2,
                             anchoredPartsVerified=4)
                with urlopen(Request(base + '/house-placement-result',
                     data=json.dumps(reply).encode('utf-8'),
                     headers={'X-Game1-Token': TOKEN, 'Content-Type': 'application/json'},
                     method='POST'), timeout=2) as response:
                    received.append(response.status)
            except Exception as error:
                faults.append(error)

        worker = threading.Thread(target=simulated_studio, daemon=True)
        worker.start()
        try:
            result = bridge.bulk_house_placements('house_a', 'place_all',
                                                  [binding(plot=1), binding(plot=3, anchored=False)],
                                                  timeout_seconds=4)
        finally:
            worker.join(timeout=4)
        self.assertEqual(faults, [])
        self.assertEqual(received[1], 200)
        self.assertEqual(received[0]['action'], 'place_all')
        self.assertEqual(received[0]['plotIndex'], 0)
        self.assertEqual(received[0]['schemaVersion'], 2)
        self.assertEqual([item['plotIndex'] for item in received[0]['targets']], [1, 3])
        self.assertEqual(result['anchoredPartsVerified'], 4)


class BulkPreviewIntegrationContract(TestCase):
    def test_ui_and_studio_use_existing_place_clear_mechanism(self):
        static = ROOT / 'system/control-center/static'
        html = (static / 'index.html').read_text(encoding='utf-8')
        js = (static / 'real-estate-placement.js').read_text(encoding='utf-8')
        plugin = (ROOT / 'system/studio-plugin/modules/StudioHousePlacementPreview.luau').read_text(encoding='utf-8')
        for element in ('re-placement-place-all', 're-placement-clear-all'):
            self.assertIn(f'id="{element}"', html)
            self.assertIn(f"$('{element}')", js)
        self.assertIn("'/api/real-estate/placements/bulk'", js)
        self.assertIn("state.house?all.filter(item=>item.houseSlug===state.house):[]", js)
        self.assertIn('const studio=response.studio', js)
        self.assertIn('local function stagePlace(', plugin)
        self.assertIn('local function executePlans(', plugin)
        self.assertIn('return executePlans({stagePlace(', plugin)
        self.assertIn('return executePlans(plans, "place_all")', plugin)
        self.assertIn('return executePlans(plans, "clear_all")', plugin)
        self.assertIn('isManagedPreview(child, index)', plugin)
        self.assertIn('ChangeHistoryService:TryBeginRecording', plugin)
        self.assertLess(plugin.index('table.insert(plans, stagePlace('),
                        plugin.index('return executePlans(plans, "place_all")'))
        self.assertLess(plugin.index('verifiedParts = setAndVerifyAnchored(clone, binding.anchored)'),
                        plugin.index('for _, previous in ipairs(plan.previous) do'))
