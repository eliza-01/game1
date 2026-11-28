"""Production-path source gates; native physics/animation remains NOT_RUN."""
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[2]

def read(path):
    return (ROOT/path).read_text(encoding='utf-8')

class RuntimeDemandM639(unittest.TestCase):
    def test_both_spawners_can_publish_shell_without_rig(self):
        for kind, model, root, path in (
            ('Monster','model','navigationRoot','monster/MonsterSpawnerService'),
            ('NPC','entity','root','npc/NpcSpawnerService'),
        ):
            source=read('src/server/'+path+'.luau')
            gate=source.index(f'Demand.CanSpawnShell({model}, {root}, template)')
            attach=source.index(f'MnpcLifecycle.AttachRig({model}, {root}, template, surface, yaw, "{kind}", prepared)')
            self.assertLess(gate,attach)
            self.assertIn('if not initialShell then',source[gate:attach])
            self.assertIn('}, initialShell, template)',source)
            self.assertIn(f'MnpcLifecycle.Publish({model}, {root},',source)
            self.assertIn(f'EntityHitboxService.Attach({model}, nextVisual)',source)
        monster=read('src/server/monster/MonsterSpawnerService.luau')
        self.assertIn('and not record.testOwner and not riseFromGround',monster)
        self.assertIn('model:SetAttribute("MonsterSpawning", not initialShell)',monster)
        npc=read('src/server/npc/NpcSpawnerService.luau')
        self.assertIn('if initialShell then\n        -- Bind registers AI',npc)
        self.assertLess(npc.index('NpcCombatAIService.Bind(entity'),npc.index('NpcCombatAIService.DetachPresentation(entity)'))
        self.assertIn('NpcCombatAIService.BeginPresentation(entity)',npc)

    def test_opt_in_readiness_and_batch_scope(self):
        demand=read('src/server/actor/MnpcDemandLifecycle.luau')
        self.assertNotIn('Game1MnpcDemandPilot',demand)
        self.assertIn('Policy.Resolve(distance, previous, profile, distance <= reach)',demand)
        self.assertNotIn('DebugAccess.ServerEnabled() then maxReach',demand)
        self.assertNotIn('PREWARM',demand)
        self.assertIn('qualified[template]',demand)
        self.assertIn('if not best or distance < bestDistance',demand.replace('elseif not best','if not best'))
        scheduler=read('src/server/actor/ActorAIScheduler.luau')
        self.assertLess(scheduler.index('pcall(Demand.Pump)'),scheduler.index('PlayerSpatialIndex.EndBatch()'))
        self.assertEqual(scheduler.count('RunService.Heartbeat:Connect'),1)
        controller=read('src/client/actor/MnpcLodController.luau')
        self.assertIn('(stage == nil or stage == "full")',controller)
        observer=read('src/client/actor/MnpcRigObserver.luau')
        self.assertIn('(demandStage == nil or demandStage == "full")',observer)
        self.assertIn('"Game1MnpcRigReady", "Game1MnpcDemandStage", "Game1MnpcLocalLod"',observer)
