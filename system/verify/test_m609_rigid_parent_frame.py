"""Contract regression; actual Roblox native solver requires Studio/DEV."""
from pathlib import Path
import json
import math
import unittest

ROOT = Path(__file__).resolve().parents[2]
def read(p): return (ROOT / p).read_text(encoding='utf-8')

# Small independent rigid-matrix reference, no third-party dependencies.
def pose(x, y, z, a, b):
    ca, sa, cb, sb = math.cos(a), math.sin(a), math.cos(b), math.sin(b)
    return ((ca, -sa*cb, sa*sb, x), (sa, ca*cb, -ca*sb, y), (0, sb, cb, z), (0, 0, 0, 1))
def mul(a, b):
    return tuple(tuple(sum(a[i][k]*b[k][j] for k in range(4)) for j in range(4)) for i in range(4))
def inv(a):
    return tuple(tuple(a[j][i] if j < 3 else -sum(a[k][i]*a[k][3] for k in range(3)) for j in range(4)) for i in range(3)) + ((0,0,0,1),)

class ParentSocket(unittest.TestCase):
    def test_native_equation_matches_old_pose_even_with_socket_animation(self):
        local = pose(1, -.7, .2, .6, .2)
        correction = pose(0, 0, 0, 0, -math.pi/2)
        grip = pose(.3, .9, -.4, -.3, .8)
        joint_grip = mul(grip, inv(mul(local, correction)))
        for parent in (pose(0, 0, 0, 0, 0), pose(10, 5, 1, 1.8, -.2), pose(-3, 13, 4, -.8, 1.3)):
            # solver must satisfy item * joint_grip = parent
            actual = mul(mul(parent, inv(joint_grip)), grip)
            expected = mul(mul(parent, local), correction)
            for a, b in zip(sum(actual, ()), sum(expected, ())): self.assertAlmostEqual(a, b, places=10)
            socket_transform = pose(2, 0, 0, .8, -.3)
            wrong = mul(mul(mul(parent, local), socket_transform), correction)
            self.assertGreater(max(abs(a-b) for a,b in zip(sum(actual,()),sum(wrong,()))), .1)
    def test_parent_contract_and_lookup(self):
        s = read('src/shared/rig/RigidEquipmentMount.luau')
        for token in ('if parent:IsA("Bone") then return parent end', 'parent.TransformedWorldCFrame * target.CFrame', 'else target.WorldCFrame', 'local offset = target.CFrame * correction(kind)', 'grip.CFrame * offset:Inverse()', 'StaticMount.Place(model, grip, Mount.SocketFrame(target, kind))', 'joint.Attachment0 = socket', 'local bone = visual:FindFirstChild(name, true)', 'findHairBone(character, name)', 'carrier:FindFirstChild(name, true)', 'endpoint.CFrame = CFrame.identity'):
            self.assertIn(token,s)
        self.assertNotIn('target.TransformedWorldCFrame',s)
        for token in ('Instance.new("Bone")','Game1RigidSocketBone','__Game1RigidSocket_', 'RenderStepped','Heartbeat','PreSimulation','PostSimulation', 'SetNetworkOwner', 'task.spawn', ':Connect('): self.assertNotIn(token,s)
        self.assertEqual(s.count('Instance.new("RigidConstraint")'),1)
    def test_consumers_follow_endpoint(self):
        s = read('src/shared/rig/RigidEquipmentMount.luau')
        self.assertIn('endpointFrame(socket) * grip.WorldCFrame:Inverse()',s)
        self.assertIn('expectedGrip:ToObjectSpace(grip.CFrame)',s)
        self.assertIn('delta:PointToWorldSpace(authored.WorldPosition)',s)
        timeline = read('system/studio-plugin/modules/StudioTimelinePreview.luau')
        self.assertIn('if endpoint:IsA("Bone") then endpoint.TransformedWorldCFrame else endpoint.WorldCFrame',timeline)
        for path in (ROOT/'src').rglob('*.luau'):
            self.assertNotIn('Game1RigidSocketBone',path.read_text(encoding='utf-8'),str(path))
    def test_owner_acceptance_and_measurements_are_distinct(self):
        c=json.loads(read('docs/kanban/cards/KBN-0037.json'))
        self.assertTrue(c['tasks'][1]['done'])
        self.assertFalse(c['tasks'][5]['done'])
        self.assertEqual(c['status'],'IN_PROGRESS')
        self.assertEqual(c['acceptance'][1]['status'],'NOT_RUN')
        self.assertIn('M607/M608 FAIL',c['acceptance'][1]['evidence'])
        self.assertIn('супер работает в рантайме и на телефоне',c['acceptance'][1]['evidence'])
        profiler=json.loads(read('docs/kanban/cards/KBN-0035.json'))
        self.assertIn(profiler['status'], ('READY', 'IN_PROGRESS', 'CODE_COMPLETE', 'DONE'))

if __name__=='__main__': unittest.main()
