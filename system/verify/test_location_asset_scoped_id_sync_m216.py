"""M216 safety regression: opt-in, single-slug ID edits, durable history, no rebuilds."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen
import json
import socket
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from api.write_world import route
from services.location_asset_sync_history import LocationAssetSyncHistory
from services import studio_deco_bridge as bridge


class MemoryAudit:
    def __init__(self):
        self.events = []
    def ensure_schema(self):
        return None
    def append(self, event):
        if not any(row['operationId'] == event['operationId'] for row in self.events):
            self.events.append(dict(event))
    def page(self, slug, *, limit, before=None):
        rows = [(index + 1, row) for index, row in enumerate(self.events)
                if row['slug'] == slug and (before is None or index + 1 < before)]
        rows.reverse()
        selected = rows[:limit]
        return {
            'events': [row for _, row in selected],
            'nextCursor': selected[-1][0] if len(rows) > limit else None,
        }


class FakeAtlas:
    marked = None
    def binding(self, _kind, slug):
        return {'variant_id': 5, 'revision': 3} if slug == 'oak_tree' else None
    def mark_synced(self, kind, slug, revision):
        self.marked = (kind, slug, revision)
        return True


class FakeAssets:
    def __init__(self):
        self.atlases = FakeAtlas()
        self.exports = 0
    def get(self, slug):
        if slug != 'oak_tree':
            return None
        return {'slug': slug, 'status': 'PUBLISHED', 'bindingRevision': 3,
                'model_asset_id': '12345', 'texture_asset_id': '98765'}
    def export(self):
        self.exports += 1


class SafetyM216(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.loc = FakeAssets()
        self.history = LocationAssetSyncHistory(Path(self.tmp.name), database=MemoryAudit())
        self.report = {'operationId': 'a' * 32, 'models': 1, 'parts': 2,
                       'matchedModels': 2, 'modelReferences': 1,
                       'pendingGeometry': 2, 'geometryUpdated': 0, 'meshPartsUpdated': 0,
                       'replacedModels': 0, 'registryItems': 26,
                       'changes': [
                           {'kind': 'model_reference', 'oldId': '10', 'newId': '12345', 'count': 1},
                           {'kind': 'atlas', 'oldId': '33', 'newId': '98765', 'count': 2},
                       ],
                       'instances': [{
                           'instanceId': 'placed_oak_01',
                           'studioPath': 'Workspace.Places.placed_oak_01',
                           'changes': [
                               {'kind': 'model_reference', 'oldId': '10', 'newId': '12345', 'count': 1},
                               {'kind': 'atlas', 'oldId': '33', 'newId': '98765', 'count': 2},
                           ],
                       }]}
        self.scoped = mock.Mock(return_value=self.report)
        self.deps = defaultdict(lambda: None, {
            'location_assets': self.loc,
            'location_asset_sync_history': self.history,
            'sync_location_assets_to_studio': self.scoped,
        })

    def source(self, path):
        return (ROOT / path).read_text(encoding='utf-8')

    def test_unscoped_sync_is_rejected_before_bridge_or_persistence(self):
        for payload in ({}, {'slug': ''}, {'slug': 'different_asset'}):
            with self.subTest(payload=payload):
                status, reply = route('/api/location-assets/studio-sync', lambda: payload, self.deps)
                self.assertEqual(status, 400, reply)
        self.scoped.assert_not_called()
        self.assertEqual(self.loc.exports, 0)
        self.assertFalse(self.history.path.exists())

    def test_only_target_slug_is_sent_and_logged(self):
        status, reply = route('/api/location-assets/studio-sync',
                              lambda: {'slug': 'oak_tree'}, self.deps)
        self.assertEqual(status, 200, reply)
        self.scoped.assert_called_once_with(slug='oak_tree', binding_revision=3,
                                            model_asset_id='12345', atlas_asset_id='98765')
        self.assertEqual(self.loc.atlases.marked, ('location_asset', 'oak_tree', 3))
        self.assertEqual(self.loc.exports, 1)
        event = self.history.list('oak_tree')[0]
        self.assertEqual(event['changes'], self.report['changes'])
        self.assertEqual(event['instances'], self.report['instances'])
        self.assertEqual(event['pendingGeometry'], 2)
        self.assertEqual(self.history.list('different_asset'), [])

    def test_history_error_cannot_mark_revision_synced(self):
        self.deps['location_asset_sync_history'] = mock.Mock()
        self.deps['location_asset_sync_history'].append.side_effect = OSError('disk full')
        status, reply = route('/api/location-assets/studio-sync',
                              lambda: {'slug': 'oak_tree'}, self.deps)
        self.assertEqual(status, 400)
        self.assertIn('disk full', reply['error'])
        self.assertIsNone(self.loc.atlases.marked)

    def test_history_is_append_only_and_validated(self):
        self.history.append(slug='oak_tree', binding_revision=3, studio=self.report)
        second = dict(self.report, operationId='b' * 32)
        self.history.append(slug='oak_tree', binding_revision=4, studio=second)
        self.assertEqual(len(self.history.list('oak_tree')), 2)
        bad = dict(self.report, changes=[{'kind': 'atlas', 'oldId': '1', 'newId': '2', 'count': -1}])
        with self.assertRaisesRegex(ValueError, 'history entry'):
            self.history.append(slug='oak_tree', binding_revision=5, studio=bad)
        self.assertEqual(len(self.history.list('oak_tree')), 2)

    def test_database_history_is_not_limited_to_last_32_or_50_events(self):
        for index in range(75):
            report = dict(self.report, operationId=f'{index:032x}')
            self.history.append(slug='oak_tree', binding_revision=index + 1, studio=report)
        events = self.history.list('oak_tree')
        self.assertEqual(len(events), 75)
        self.assertEqual(events[0]['operationId'], f'{74:032x}')
        self.assertEqual(events[-1]['operationId'], f'{0:032x}')

    def test_published_atlas_has_no_implicit_studio_sync(self):
        source = self.source('system/control-center/api/write_world.py')
        republish = source.split("if path.startswith('/api/texture-atlases/variants/') and path.endswith('/republish'):")[1].split("if path.startswith('/api/texture-atlases/variants/') and path.endswith('/publish'):")[0]
        self.assertNotIn("deps['sync_location_assets_to_studio']", republish)
        self.assertNotIn("deps['sync_real_estate_to_studio']", republish)
        self.assertIn('requiresExplicitStudioSync', republish)

    def test_plugin_has_no_destructive_update_operations(self):
        sync = self.source('system/studio-plugin/modules/DecoPlacedAssetSync.luau')
        manager = self.source('system/studio-plugin/modules/DecoManager.luau')
        command = self.source('system/studio-plugin/modules/StudioDecoSyncCommands.luau')
        self.assertIn('schemaVersion ~= 6', command)
        self.assertIn('command.targetSlug', command)
        self.assertIn('DecoPlacedAssetSync.RefreshIds(', manager)
        self.assertNotIn('DecoPlacedAssetSync.RefreshModels(', manager)
        for forbidden in ('previous:Destroy()', 'replacement:Destroy()',
                          'LoadAssetAsync(', '.MeshId =', '.CFrame =', '.Size ='):
            self.assertNotIn(forbidden, sync)
        self.assertIn('RigSwap.Prepare(', sync)
        self.assertIn('RigSwap.Commit(', sync)
        self.assertIn('RigSwap.Rollback(', sync)
        self.assertNotIn('model:Destroy()', sync)
        self.assertIn('StudioTextureAppearance.Apply(change.part, uri, nil, true)', sync)
        appearance = self.source('system/studio-plugin/modules/StudioTextureAppearance.luau')
        self.assertIn('if idsOnly == true then', appearance)
        self.assertIn('mesh.TextureID = uri', appearance)
        self.assertIn('surface.ColorMap = uri', appearance)
        self.assertIn('Game1DecoSyncHistory', sync)
        self.assertIn('Game1DecoRegistryModelAssetId', sync)
        self.assertIn('Game1DecoPublishedModelSha256', sync)
        self.assertIn('studioPath = item.model:GetFullName()', sync)
        self.assertIn('instances = instances', sync)
        self.assertIn('"changes", "instances"', command)

    def test_sync_finds_legacy_places_by_stable_identity_without_reparenting(self):
        sync = self.source('system/studio-plugin/modules/DecoPlacedAssetSync.luau')
        discovery = sync.split('local function targets(', 1)[1].split(
            'local function meshParts(', 1)[0]
        self.assertIn('workspace:GetDescendants()', discovery)
        self.assertIn('descendant:GetAttribute(SLUG) == slug', discovery)
        self.assertIn('descendant:GetAttribute(INSTANCE)', discovery)
        self.assertNotRegex(discovery, r'\.Parent\s*=(?!=)')

    def test_ui_scopes_sync_and_shows_history(self):
        js = self.source('system/control-center/static/deco-assets.js')
        html = self.source('system/control-center/static/index.html')
        self.assertIn("window.game1StudioSync.run('location', slug)", js)
        self.assertIn("tr.querySelector('[data-deco-sync]').onclick = () => decoAssetSyncStudio(row.slug)", js)
        self.assertIn('decoAssetShowSyncHistory', js)
        self.assertIn('location-asset-studio-history', html)
        self.assertNotIn("request('/api/location-assets/studio-sync', { method: 'POST' })", js)

    @staticmethod
    def _request(port, path, method='GET', data=None):
        encoded = json.dumps(data).encode() if data is not None else None
        headers = {'X-Game1-Token': bridge.TOKEN}
        if encoded is not None:
            headers['Content-Type'] = 'application/json'
        with urlopen(Request(f'http://127.0.0.1:{port}{path}', data=encoded,
                             headers=headers, method=method), timeout=3) as response:
            return json.load(response)

    def test_bridge_schema_4_roundtrip_and_old_command_rejection(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        result = {}
        def runner():
            try:
                result['value'] = bridge.run_deco_refresh_bridge(
                    timeout_seconds=5, slug='oak_tree', binding_revision=3,
                    model_asset_id='12345', atlas_asset_id='98765')
            except Exception as error:
                result['error'] = str(error)
        with mock.patch.object(bridge, 'PORT', port):
            thread = threading.Thread(target=runner, daemon=True)
            thread.start()
            command = None
            for _ in range(200):
                try:
                    command = self._request(port, '/command')
                    break
                except (URLError, OSError):
                    time.sleep(.01)
            self.assertEqual(command['schemaVersion'], 6)
            self.assertEqual(command['targetSlug'], 'oak_tree')
            with self.assertRaises(HTTPError):
                self._request(port, '/deco-refresh-result', 'POST', {
                    **command, 'schemaVersion': 2, **self.report})
            self._request(port, '/deco-refresh-result', 'POST', {
                **command, **{k: v for k, v in self.report.items() if k != 'operationId'}})
            thread.join(5)
            self.assertFalse(thread.is_alive())
        self.assertNotIn('error', result)
        self.assertEqual(result['value']['changes'], self.report['changes'])
        self.assertEqual(result['value']['instances'], self.report['instances'])
        self.assertEqual(result['value']['operationId'], command['operationId'])


if __name__ == '__main__':
    import unittest
    unittest.main()
