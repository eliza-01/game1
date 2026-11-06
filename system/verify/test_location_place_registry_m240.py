"""M240: dedicated Location-only inventory and immutable revision contracts."""
from __future__ import annotations

import json
import socket
import sys
import threading
import time
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services.place_registry.catalog import build_catalog, validate_report
from services.place_registry.revisions import PlaceRevisionStore
from services.place_registry.coordinator import LocationPlaceRegistry
from services import studio_place_registry_bridge as bridge
from api.write_world import route


class FakeAssets:
    def __init__(self):
        self.cache = []

    def snapshot(self):
        return {'items': [
            {'slug': 'stone_fence_01', 'status': 'PUBLISHED', 'model_asset_id': '300',
             'texture_asset_id': '999', 'model_published_sha256': 'sha1'},
            {'slug': 'birch_01', 'status': 'UPDATE_AVAILABLE', 'model_asset_id': '500',
             'texture_asset_id': '888', 'model_published_sha256': 'sha2'},
            {'slug': 'unpublished', 'status': 'REGISTERED', 'model_asset_id': '',
             'texture_asset_id': ''},
        ]}

    def model_publication_ids(self, slug):
        return {'stone_fence_01': ['300', '200'], 'birch_01': ['500']}[slug]

    def mesh_id_inventory(self, slug):
        return {'stone_fence_01': [
            {'modelAssetId': '200', 'meshes': [{'meshId': '101', 'count': 1,
                                                 'visualNames': ['stone_fence_01']}]},
            {'modelAssetId': '300', 'meshes': [{'meshId': '102', 'count': 1,
                                                 'visualNames': ['stone_fence_01']},
                                                {'meshId': '103', 'count': 1, 'visualNames': []}]}],
            'birch_01': [{'modelAssetId': '500', 'meshes': [
                {'meshId': '401', 'count': 1, 'visualNames': ['birch_01']}]}],
        }[slug]

    def record_mesh_id_inventory(self, slug, records):
        self.cache.append((slug, records))


def row():
    return {'key': 'p1', 'name': 'stone_fence_01', 'path': 'Workspace.Fences.1',
            'slug': 'stone_fence_01', 'placementId': '', 'meshId': '101',
            'textureId': '999', 'status': 'pending', 'transform': {'cframe': [1] * 12,
            'size': [1, 2, 3]}, 'needsMesh': True, 'needsTexture': False,
            'needsStructure': True, 'duplicateId': False, 'ambiguous': False,
            'hasModel': False, 'canSync': False, 'issues': ['Нет Model']}


class PlaceRegistryM240(TestCase):
    def test_only_published_location_allowlist_and_cached_visual_roles(self):
        c = build_catalog(FakeAssets())
        self.assertEqual(c['domain'], 'location_assets')
        self.assertEqual([x['slug'] for x in c['items']], ['birch_01', 'stone_fence_01'])
        self.assertEqual([x['modelAssetId'] for x in c['items'][1]['models']], ['300', '200'])
        self.assertEqual(c['items'][1]['models'][0]['meshes'][1]['visualNames'], [])
        copy = FakeAssets()
        copy.record_mesh_id_inventory('stone_fence_01', [])
        self.assertEqual(build_catalog(copy)['digest'], c['digest'])
        modified = FakeAssets()
        old_snapshot = modified.snapshot
        def altered():
            value = old_snapshot()
            value['items'][0]['texture_asset_id'] = '777'
            return value
        modified.snapshot = altered
        self.assertNotEqual(build_catalog(modified)['digest'], c['digest'])

    def test_report_rejects_unknown_slugs_duplicate_keys_and_foreign_data(self):
        catalog = build_catalog(FakeAssets())
        report = {'schemaVersion': 1, 'placeId': 0, 'placements': [row()]}
        self.assertEqual(len(validate_report(report, catalog)), 1)
        for bad in ({'slug': 'house_level5_01'}, {'key': 'p0'}, {'canSync': None}):
            invalid = deepcopy(report)
            invalid['placements'][0].update(bad)
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_report(invalid, catalog)
        invalid = deepcopy(report)
        invalid['placements'].append(deepcopy(invalid['placements'][0]))
        with self.assertRaises(ValueError):
            validate_report(invalid, catalog)

    def test_revision_is_append_only_and_survives_restart(self):
        with TemporaryDirectory() as tmp:
            registry = PlaceRevisionStore(tmp)
            report = {'schemaVersion': 1, 'placeId': 42, 'placements': [row()]}
            first = registry.add(report, 'source')
            self.assertTrue(first['recorded'])
            again = registry.add(report, 'source')
            self.assertEqual(first['revisionId'], again['revisionId'])
            self.assertTrue(again['unchanged'])
            changed = deepcopy(report)
            changed['placements'][0]['textureId'] = '123'
            second = registry.add(changed, 'source')
            self.assertEqual(second['revisionId'], first['revisionId'] + 1)
            registry = PlaceRevisionStore(tmp)
            self.assertEqual(registry.get(first['revisionId']), report)
            self.assertEqual(registry.get(second['revisionId']), changed)
            diff = registry.diff(first['revisionId'], second['revisionId'])
            self.assertEqual((diff['added'], diff['removed']), (1, 1))
            registry.log_action(first['revisionId'], 'repair', {'changed': 1})
            with self.assertRaises(ValueError):
                registry.log_action(first['revisionId'], 'scan', {'changed': 1})

    def test_coordinator_requires_one_token_explicit_keys_and_rescans_after_repair(self):
        assets = FakeAssets()
        catalog = build_catalog(assets)
        with TemporaryDirectory() as tmp:
            def studio(**kwargs):
                if kwargs['phase'] == 'scan':
                    return {'catalogDigest': kwargs['catalog']['digest'], 'scanToken': 'a'*32,
                            'scan': {'schemaVersion': 1, 'placeId': 42,
                                     'placements': [row()], 'warnings': []},
                            'inventory': []}
                return {'operationId': 'b'*32, 'result': {'changed': 1, 'undo': True}}
            transport = mock.Mock(side_effect=studio)
            app = LocationPlaceRegistry(assets, PlaceRevisionStore(tmp), transport)
            scan = app.operate('scan')
            self.assertEqual(scan['summary']['outdatedMesh'], 1)
            with self.assertRaises(ValueError):
                app.operate('repair', scan_token='b'*32, keys=['p1'])
            result = app.operate('repair', scan_token='a'*32, keys=['p1'])
            self.assertEqual(result['changed'], 1)
            with self.assertRaises(ValueError):
                app.operate('repair', scan_token='a'*32, keys=['p1'])
            self.assertEqual(transport.call_count, 2)

    def test_bridge_requires_signed_identity_and_scanned_keys(self):
        catalog = build_catalog(FakeAssets())
        for kwargs in ({'phase': 'repair', 'scan_token': '', 'keys': ['p1']},
                       {'phase': 'sync', 'scan_token': 'a'*32, 'keys': []},
                       {'phase': 'select', 'scan_token': 'a'*32, 'keys': ['p1', 'p1']},
                       {'phase': 'delete', 'scan_token': 'a'*32, 'keys': ['p1']}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                bridge.run_place_registry_bridge(catalog=catalog, **kwargs)

    def test_bridge_single_claim_and_response_roundtrip(self):
        catalog = build_catalog(FakeAssets())
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        results = {}
        def run():
            try:
                results['value'] = bridge.run_place_registry_bridge(
                    catalog=catalog, phase='scan', timeout_seconds=5)
            except Exception as e:
                results['error'] = e
        with mock.patch.object(bridge, 'PORT', port):
            worker = threading.Thread(target=run, daemon=True)
            worker.start()
            command = None
            for _ in range(200):
                try:
                    with urlopen(Request(f'http://127.0.0.1:{port}/command',
                            headers={'X-Game1-Token': bridge.TOKEN}), timeout=1) as answer:
                        command = json.load(answer)
                    break
                except (URLError, OSError):
                    time.sleep(.01)
            self.assertIsNotNone(command)
            self.assertEqual(command['catalog']['domain'], 'location_assets')
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(f'http://127.0.0.1:{port}/command',
                               headers={'X-Game1-Token': bridge.TOKEN}), timeout=1)
            self.assertEqual(error.exception.code, 409)
            response = {'project': bridge.PROJECT, 'command': 'location-place-registry',
                        'schemaVersion': 1, 'operationId': command['operationId'],
                        'catalogDigest': catalog['digest'], 'phase': 'scan',
                        'scanToken': 'a'*32, 'scan': {'schemaVersion': 1, 'placeId': 42,
                        'placements': [row()]}, 'inventory': []}
            with urlopen(Request(f'http://127.0.0.1:{port}/place-registry-result',
                    data=json.dumps(response).encode(), method='POST', headers={
                        'X-Game1-Token': bridge.TOKEN}), timeout=1) as answer:
                self.assertTrue(json.load(answer)['ok'])
            worker.join(5)
            self.assertNotIn('error', results)
            self.assertEqual(results['value']['scanToken'], 'a'*32)

    def test_ui_and_studio_contract_no_cross_domain_write(self):
        web = (ROOT / 'system/control-center/static/place-registry.js').read_text('utf8')
        scanner = (ROOT / 'system/studio-plugin/modules/StudioPlaceRegistryInventory.luau').read_text('utf8')
        sync = (ROOT / 'system/studio-plugin/modules/StudioPlaceRegistrySync.luau').read_text('utf8')
        self.assertIn("phase==='scan'", web)
        self.assertIn('Game1DecoInstanceId', scanner)
        self.assertIn('if catalog.domain~="location_assets"', scanner)
        self.assertIn('local byMesh=signatures(versions)', scanner)
        self.assertIn('RigSwap.Prepare(', sync)
        self.assertIn('RigSwap.Rollback(', sync)
        self.assertNotIn('ApplyMesh(', sync)
        self.assertNotIn('DestroyAllChildren', sync)

    def test_write_endpoint_is_independent_of_other_domain_deps(self):
        result = mock.Mock()
        result.operate.return_value = {'scanToken': 'a'*32}
        self.assertEqual(route('/api/location-place-registry', lambda: {'phase':'scan'},
                               {'place_registry': result})[0], 200)
        result.operate.assert_called_once_with('scan', scan_token='', keys=None)
