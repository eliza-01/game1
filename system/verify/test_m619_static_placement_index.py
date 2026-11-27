"""M619: local pivot candidates, old policy and visual ownership contracts."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


class StaticPlacementIndexM619(unittest.TestCase):
    def test_index_candidate_lifecycle_and_full_scan_oracle(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua:
            self.skipTest('Lua CLI unavailable; run standalone Lua oracle when installed')
        subprocess.run([lua, 'system/verify/static_placement_index_m619.lua'], cwd=ROOT, check=True, timeout=30)

    def test_existing_policy_and_preview_regression_baseline(self):
        for path, digest in {
            'src/shared/world/LocationLodDistancePolicy.luau': 'b30f83c16c45d73f1ab34543a278860038b123b2fda2fd7531f4ab2bf8312515',
            'src/client/world/StudioLodPreviewAdapter.luau': 'd27f3cbfa1e3bc9fce85178b15206fe5075e176842ac659719764eb408675100',
        }.items():
            self.assertEqual(hashlib.sha256(read(path).encode()).hexdigest(), digest, path)

    def test_runtime_integration_and_no_full_scan(self):
        source = read('src/client/world/LocationWorldStreamer.luau')
        tick = source.split('RunService.Heartbeat:Connect', 1)[1]
        self.assertNotIn('ipairs(records)', tick)
        self.assertNotIn('table.sort(records', source)
        for needle in ('candidates:Collect(cameraPosition, cameraChanged)', 'LodThresholdCache.Resolve(record, cameraPosition, Policy, cameraChanged)',
                       'queue:Ordered(function(record, position)', 'candidates:Retain(localRecords)',
                       'compositeEffects:ActualChanged(record)',
                       'record.part:IsDescendantOf(Workspace)', 'houseAdapter:Observe(record, previousDesired, queue)'):
            self.assertIn(needle, tick)
        self.assertEqual(source.count('RunService.Heartbeat:Connect'), 1)
        self.assertIn('local TICK = 0.25', source)
        self.assertIn('local VISUAL_INTERVAL = 1', source)
        self.assertIn('StaticPlacementIndex.new(records)', source.split('RunService.Heartbeat:Connect', 1)[0])
        self.assertIn('"$path": "src/client"', read('default.project.json'))
        for name in ('StaticPlacementIndex', 'LocationLodCandidates'):
            module = read('src/client/world/' + name + '.luau')
            for forbidden in ('Heartbeat', 'Raycast', 'RemoteEvent', 'Instance.new', 'GetDescendants'):
                self.assertNotIn(forbidden, module)

    def test_mechanics_runtime_lod_sources(self):
        from api.mechanics import route
        from mechanics.catalog import snapshot
        domain = next(d for d in snapshot()['domains'] if d['id'] == 'lod')
        card = domain['items'][0]
        for source in card['sources']:
            status, payload = route(urlparse(f'/api/mechanics/source?item={card["id"]}&source={source["id"]}'))
            self.assertEqual(status, 200, source['id'])
            self.assertEqual(payload['path'], source['path'])
        self.assertEqual(route(urlparse('/api/mechanics/source?item=runtime-lod-streaming&source=monster-ai'))[0], 404)
