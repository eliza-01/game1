"""M627 diagnostic contract. No claim of native Roblox animation execution."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / 'src/shared/dev/MnpcPoseProbe.luau'
SERVER = ROOT / 'src/server/dev/MnpcPoseProbeService.luau'
CLIENT = ROOT / 'src/client/dev/MnpcPoseProbeController.luau'


class MnpcPosePilotM627(unittest.TestCase):
    def test_manual_studio_gate_and_no_bootstrap_registration(self):
        self.assertIn('RunService:IsStudio() and RunService:IsRunning()', SHARED.read_text())
        for path, method, side in [(SERVER, 'Start()', 'IsServer()'), (CLIENT, 'Observe(mode: string)', 'IsClient()')]:
            text = path.read_text()
            self.assertIn(method, text)
            self.assertIn('Probe.AssertStudio()', text)
            self.assertIn(side, text)
            for token in ('RemoteEvent', 'RemoteFunction', 'Heartbeat:Connect', 'RenderStepped:Connect'):
                self.assertNotIn(token, text)
        for path in (ROOT/'src').rglob('*.luau'):
            if path not in (SERVER, CLIENT, SHARED):
                self.assertNotIn('MnpcPoseProbe', path.read_text(encoding='utf-8-sig'), str(path))

    def test_fixture_isolation_and_skeleton_path_guard(self):
        text = SHARED.read_text()
        for token in ('source:Clone()', 'Instance.new("Part")', 'copyBones(source, part)',
                      'child:Destroy()', 'CollectionService:RemoveTag', 'instance:SetAttribute(key, nil)',
                      'part.Anchored = true', 'part.CanCollide = false', 'part.CanTouch = false',
                      'part.CanQuery = false', 'part.Transparency = 1', 'duplicate bone path',
                      'unsupported/missing source bone', 'unexpected copied bone', 'model:Destroy(); error(err)',
                      'bone.TransformedWorldCFrame'):
            self.assertIn(token, text)

    def test_engine_observations_and_cleanup_are_explicit(self):
        text = SERVER.read_text()
        for token in ('Game1MonsterRuntime', 'Game1NpcRuntime', 'WeightCurrent > 0.5',
                      'SKIPPED_NO_ACTIVE_ACTOR', 'INCONCLUSIVE_REFERENCE_STATIC', 'CARRIER_MISMATCH',
                      'delta.missing == 0', 'delta.maxStuds <= 0.01', 'delta.maxDegrees <= 0.5',
                      'PRIVATE_LOAD', 'MOVE_TO_PRIVATE', 'REPLICATED_CARRIER',
                      'private:Destroy()', 'moved:Destroy()', 'refAnimator.Parent:Destroy()',
                      'world:Destroy()', 'templates:Destroy()', 'task.wait(60)'):
            self.assertIn(token, text)
        client = CLIENT.read_text()
        for token in ('mode == "FULL"', 'mode == "NONE"', 'NO_OWNED_RIG',
                      'source:Clone()', 'Probe.Motion(carrier, 2)', 'localRig:Destroy()', 'SKIPPED_NOT_READY'):
            self.assertIn(token, client)
        self.assertIn('EvaluationThrottled', SHARED.read_text())

    def test_compare_math_with_fake_frames(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua:
            self.skipTest('Lua CLI unavailable')
        text = SHARED.read_text()
        method = text[text.index('function Probe.Compare('):text.index('\nfunction Probe.Load(')]
        method = method.replace('function Probe.Compare(a: {[string]: CFrame}, b: {[string]: CFrame}): any',
                                'function Probe.Compare(a, b)')
        method = method.replace('missing += 1', 'missing = missing + 1').replace('count += 1', 'count = count + 1')
        script = '''local Probe = {}\n''' + method + '''
local function frame(p, r)
    return {ToObjectSpace = function(_, other)
        return {Position = {Magnitude = math.abs(other.p-p)},
                ToAxisAngle = function() return nil, math.rad(other.r-r) end}
    end, p=p, r=r}
end
local a = {head=frame(0,0), arm=frame(1,10)}
local b = {head=frame(.005,.1), arm=frame(1.02,9)}
local delta = Probe.Compare(a,b)
assert(delta.bones==2 and delta.missing==0)
assert(math.abs(delta.maxStuds-.02)<1e-9 and math.abs(delta.maxDegrees-1)<1e-9)
local missing = Probe.Compare(a,{head=frame(0,0), other=frame(0,0)})
assert(missing.bones==1 and missing.missing==2)
local empty = Probe.Compare({}, {})
assert(empty.bones==0 and empty.missing==0)
local same = Probe.Compare(a,a)
assert(same.bones==2 and same.maxStuds==0 and same.maxDegrees==0)
'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'compare.lua'
            path.write_text(script)
            subprocess.run([lua, str(path)], check=True, timeout=15)

    def test_audit_does_not_claim_engine_acceptance(self):
        import json
        card = json.loads((ROOT/'docs/kanban/cards/KBN-0037.json').read_text())
        self.assertFalse(next(t for t in card['tasks'] if t['id'].endswith('T08'))['done'])
        acceptance = next(a for a in card['acceptance'] if a['id'].endswith('A07'))
        self.assertEqual(acceptance['status'], 'NOT_RUN')
        self.assertIn('M627', acceptance['evidence'])
        self.assertIn('NOT_RUN', (ROOT/'docs/workflows/M627_MNPC_POSE_PILOT_RU.md').read_text())
