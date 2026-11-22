"""Existing persisted settings feed the complete read-only Studio preview."""
import json
import re
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlsplit
from test_m414_house_part_distances import fixture, HOUSE
from test_location_lod_manager import Assets, Registry, PlaceRevisionStore
from real_estate.store import RealEstateStore
from services.house_part_distances import ensure_schema
from services.location_lod_manager import LocationLodManager
from services.lod_studio_preview import published_id
from api.read_world import route
from api.real_estate import write

ROOT = Path(__file__).resolve().parents[2]

class StudioPreview(unittest.TestCase):
    def test_each_save_changes_complete_profile_without_scan_or_build(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            houses = RealEstateStore(root)
            fixture(houses)
            ensure_schema(houses)
            registry = Registry(PlaceRevisionStore(root))
            assets = Assets()
            manager = LocationLodManager(assets, registry, houses)
            def read():
                status, result = route(urlsplit('/api/lod-manager/studio-preview'),
                                       {'lod_manager': manager}, None)
                self.assertEqual(status, 200, result)
                return result
            first = read()
            # The actual HTTP payload must be accepted by both Studio transport
            # and shared client/server decoder. M427 updated only the latter.
            bridge = (ROOT / 'system/studio-plugin/modules/StudioLodPreviewBridge.luau').read_text()
            contract = (ROOT / 'src/shared/world/StudioLodPreviewContract.luau').read_text()
            for source in (bridge, contract):
                versions = re.findall(r'data\.schemaVersion\s*~=\s*(\d+)', source)
                self.assertEqual(versions, [str(first['schemaVersion'])])
            self.assertIn('warnOnce("unsupported profile schema ', bridge)
            self.assertEqual(first, read())
            self.assertEqual(first['locations']['stone_fence_02']['lod1'], '91896785734146')
            self.assertEqual(first['houses'][HOUSE]['parts']['roof']['hide'], 600)
            path = f'/api/real-estate/{HOUSE}/parts/roof/distances'
            status, result = write(path, lambda: {'distances': {'lod1': 50, 'hide': 40},
                                                   'expectedRevision': 1}, {'real_estate': houses})
            self.assertEqual(status, 200, result)
            updated = read()
            self.assertNotEqual(updated['digest'], first['digest'])
            self.assertEqual(updated['houses'][HOUSE]['parts']['roof'],
                             {'lod1': 20, 'hide': 41, 'assetId': ''})
            self.assertEqual(updated['houses'][HOUSE]['parts']['walls_outside'],
                             first['houses'][HOUSE]['parts']['walls_outside'])
            self.assertEqual(updated['locations'], first['locations'])
            status, _ = write(f'/api/real-estate/{HOUSE}/runtime-profile',
                              lambda: {'profile': {'mode': 'off'}, 'expectedRevision': 2},
                              {'real_estate': houses})
            self.assertEqual(status, 200)
            manager.streaming_config.save({'modes': {'stone_fence_02': 'off'},
                'assetDistances': {'stone_fence_02': {'lod1': 100, 'lod2': 200, 'hide': 500}}, 'hysteresis': 10},
                [a['slug'] for a in assets.items])
            latest = read()
            self.assertEqual(latest['houses'][HOUSE]['mode'], 'off')
            self.assertEqual(latest['houses'][HOUSE]['parts']['roof']['hide'], 41)
            self.assertEqual(latest['locations']['stone_fence_02']['mode'], 'off')
            self.assertEqual(latest['locations']['stone_fence_02']['distances']['hide'], 500)
            self.assertEqual(registry.calls, 0)
            self.assertIsNone(manager._preflight)
            self.assertFalse(manager.builder.source.exists())
            self.assertNotIn('workspace', latest)
            self.assertNotIn('sourcePath', json.dumps(latest))

    def test_only_current_published_lod_ids_are_sent(self):
        for status in ('FULL_CHANGED', 'STAGED', 'SOURCE_MISSING', 'UPDATE_AVAILABLE'):
            self.assertEqual(published_id({'status': status, 'modelAssetId': '123456'}), '')
        self.assertEqual(published_id({'status': 'PUBLISHED', 'modelAssetId': '123456'}), '123456')
        self.assertEqual(published_id({'status': 'PUBLISHED', 'modelAssetId': '9007199254740992'}), '')
        self.assertEqual(published_id({'status': 'PUBLISHED', 'modelAssetId': 'bad'}), '')

    def test_studio_only_single_scheduler_and_prototype_loader(self):
        def read(path): return (ROOT / path).read_text(encoding='utf-8')
        streamer = read('src/client/world/LocationWorldStreamer.luau')
        preview = read('src/client/world/StudioLodPreviewAdapter.luau')
        bridge = read('system/studio-plugin/modules/StudioLodPreviewBridge.luau')
        templates = read('src/server/world/StudioLodPreviewTemplates.luau')
        self.assertEqual(streamer.count('RunService.Heartbeat:Connect'), 1)
        self.assertIn('if not marker and RunService:IsStudio()', streamer)
        self.assertIn('preview:Step(MAX_CHANGES_PER_TICK)', streamer)
        self.assertIn('preview:Owns(part)', streamer)
        self.assertIn('Policy.ResolveHouse(', preview)
        self.assertIn('Policy.Resolve(', preview)
        self.assertIn('Policy.SurfaceDistance(', preview)
        self.assertIn('if record.mode == "off" then', preview)
        self.assertIn('if desired == "FULL" then original else 1', preview)
        self.assertIn('if not nextRecord then restore(old)', preview)
        self.assertNotIn('Heartbeat:Connect', preview)
        self.assertNotIn('CanCollide =', preview)
        self.assertNotIn('part:Destroy()', preview)
        self.assertIn('run:IsStudio() and run:IsRunning() and run:IsServer()', bridge)
        self.assertIn('Game1LocationRuntimeManifest', bridge)
        self.assertIn('Method = "GET"', bridge)
        self.assertIn('pcall(loadPrototype', templates)
        self.assertNotIn('LoadAssetAsync', templates)
        self.assertIn('Runtime.MarkerName', templates)
        plugin = json.loads(read('system/studio-plugin/plugin.project.json'))
        self.assertIn('StudioLodPreviewBridge', plugin['tree']['modules'])

if __name__ == '__main__': unittest.main()
