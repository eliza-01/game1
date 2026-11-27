from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
def read(path): return (ROOT / path).read_text(encoding='utf-8')

class ActorSamplerPool(unittest.TestCase):
    def test_pool_behavior(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua: self.skipTest('Lua CLI unavailable')
        subprocess.run([lua, 'system/verify/sampler_pool_m613.lua'], cwd=ROOT, check=True, timeout=15)

    def test_shared_resident_cap(self):
        self.assertIn('Pool.new(Config.MaxComposedActors, Config.SamplerIdleTtlSeconds, os.clock)', read('src/client/actor/ActorSamplerPool.luau'))
        self.assertIn('MaxComposedActors = 32', read('src/client/actor/ActorAnimationCompositionConfig.luau'))
        for path in ('actor/NpcAttackLocomotionController', 'monster/MonsterAttackLocomotionController'):
            src = read('src/client/' + path + '.luau')
            for text in ('ActorSamplerPool', 'Pool:Acquire(', 'Pool:Release(', 'Pool:Cleanup(', 'entry.acquiring', 'entries[entry.model] ~= entry', 'model.AncestryChanged:Connect'):
                self.assertIn(text, src)
            self.assertNotIn('activeCount <', src)
            self.assertNotIn('local recycled =', src)
            self.assertNotIn('local samplers =', src)
            self.assertEqual(src.count('RunService.PreSimulation:Connect'), 1)

    def test_combat_exit_keeps_lease_reachable_until_release(self):
        src = read('src/client/monster/MonsterAttackLocomotionController.luau')
        self.assertIn('setEntryActive(entry, entry.sampler ~= nil or model:GetAttribute("MonsterCombatActive") == true', src)
        self.assertIn('if entry.weight <= 0 and not wantsComposition then', src)
        self.assertIn('releaseSampler(entry)', src)
        sampler = read('src/client/actor/ActorLocomotionSampler.luau')
        self.assertIn('object:IsA("RigidConstraint")', sampler)
        self.assertNotIn('users =', sampler)
