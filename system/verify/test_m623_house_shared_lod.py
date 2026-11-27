"""M623: real estate shares the spatial index, queue and work budget."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]


def read(name):
    return (ROOT / 'src/client/world' / name).read_text(encoding='utf-8')


class HouseSharedLodM623(unittest.TestCase):
    def test_mixed_index_and_async_lifecycle(self):
        self.oracle('house_runtime_m623.lua')

    def test_adapter_atomic_swap_and_proxy_lifecycle(self):
        self.oracle('house_adapter_m623.lua')

    def oracle(self, filename):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua:
            self.skipTest('Lua CLI unavailable')
        subprocess.run([lua, 'system/verify/' + filename], cwd=ROOT, check=True, timeout=30)

    def test_single_shared_scheduler_and_independent_parts(self):
        streamer = read('LocationWorldStreamer.luau')
        house = read('HouseVisualAdapter.luau')
        self.assertLess(streamer.index('HouseVisualAdapter.new('), streamer.index('StaticPlacementIndex.new(records)'))
        self.assertIn('records[#records+1] = visual', house)
        self.assertIn('worldSize=Vector3.new(table.unpack(spec.size))*row.scale', house)
        self.assertIn('localFrame.Position * row.scale', house)
        self.assertIn('record.worldSize.Magnitude * 0.5', read('StaticPlacementIndex.luau'))
        for name in ('Observe', 'Prepare', 'Valid', 'Failed', 'Commit'):
            self.assertIn('houseAdapter:' + name + '(', streamer)
        self.assertNotIn('houseAdapter:Step(', streamer)
        self.assertNotIn('houseAdapter:Resolve(', streamer)
        self.assertEqual(streamer.count('RunService.Heartbeat:Connect'), 1)
        for forbidden in ('table.sort', 'RunService', 'RenderStepped', 'GetDescendants'):
            self.assertNotIn(forbidden, house)
        self.assertIn('for visual in pairs(self.moving)', house)

    def test_acquisition_never_publishes_and_unbind_is_identity_guarded(self):
        requests = read('HouseMeshRequests.luau')
        house = read('HouseVisualAdapter.luau')
        self.assertNotIn('.Parent', requests)
        self.assertIn('MAX_PENDING = 4', requests)
        self.assertIn('RETRY_SECONDS = 15', requests)
        self.assertIn('job:Own(acquired)', house)
        self.assertIn('work:Retire(visual.part)', house)
        self.assertIn('self:_proxy(visual) ~= job.proxy', house)
        self.assertIn('if visuals[proxy] == mesh then visuals[proxy] = nil end', read('DoorInteractionRaycast.luau'))
        prepare = house.split('function Adapter:Prepare', 1)[1].split('function Adapter:Failed', 1)[0]
        self.assertNotIn('.Parent =', prepare)


if __name__ == '__main__':
    unittest.main()
