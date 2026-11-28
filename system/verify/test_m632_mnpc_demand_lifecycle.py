"""Shared Studio pilot lifecycle. Lua doubles are not native animation/physics acceptance."""
from pathlib import Path
import shutil
import subprocess
import unittest
ROOT = Path(__file__).resolve().parents[2]

def read(path):
    return (ROOT / path).read_text(encoding='utf-8')

class MnpcDemandM632(unittest.TestCase):
    def test_shared_demand_oracle(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua:
            self.skipTest('Standalone Lua unavailable')
        subprocess.run([lua, str(ROOT/'system/verify/mnpc_demand_m632.lua'),
                        str(ROOT/'src/server/actor/MnpcDemandLifecycle.luau')], check=True, timeout=15)

    def test_common_scheduler_and_pilot_gate(self):
        demand = read('src/server/actor/MnpcDemandLifecycle.luau')
        scheduler = read('src/server/actor/ActorAIScheduler.luau')
        self.assertIn('STUDIO and Workspace:GetAttribute("Game1MnpcDemandPilot") == true', demand)
        self.assertIn('PlayerIndex.Query(root.Position, radius)', demand)
        self.assertIn('Demand.Step(current, now)', scheduler)
        self.assertEqual(scheduler.count('RunService.Heartbeat:Connect'), 1)
        for forbidden in ('Heartbeat:Connect', 'task.wait(', 'RemoteEvent', 'GetPlayers('):
            self.assertNotIn(forbidden, demand)
        self.assertIn('not activeBuild', demand)
        self.assertIn('if not pilot and record.stage == "full"', demand)

    def test_live_release_and_rebind_both_domains(self):
        monster = read('src/server/monster/MonsterSpawnerService.luau')
        npc = read('src/server/npc/NpcSpawnerService.luau')
        for source, name, root, kind in ((monster,'model','navigationRoot','Monster'), (npc,'entity','root','NPC')):
            self.assertIn(f'Demand.Register({name}', source)
            self.assertIn(f'Demand.Remove({name})', source)
            self.assertIn(f'local nextVisual, nextLease = MnpcLifecycle.AttachRig({name}, {root}, template, surface, yaw, "{kind}", prepared)', source)
            self.assertIn(f'EntityHitboxService.Attach({name}, nextVisual)', source)
            self.assertIn(f'if not alive() then pcall(EntityHitboxService.Detach, {name}); return false end', source)
        mrelease = monster.split('local function releaseLivePose',1)[1].split('local function spawnOne',1)[0]
        nrelease = npc.split('Demand.Register(entity',1)[1].split('acquire = function',1)[0]
        for release, token, name in ((mrelease,'MonsterAgentLifecycle.DetachPose(model)','model'),(nrelease,'NpcCombatAIService.DetachPresentation(entity)','entity')):
            positions = [release.index(x) for x in (f'{name}:SetAttribute("Damageable", false)',token,f'EntityHitboxService.Detach({name})','entry.rigLease:Release()')]
            self.assertEqual(positions,sorted(positions))
            self.assertNotIn(f'{name}:Destroy()',release)
        self.assertIn('entry.idleConnections == connections', monster)
        self.assertIn('NpcCombatAIService.BeginPresentation(entity)', npc)
        self.assertIn('NpcCombatAIService.AttachPresentation(entity, ticket, nextPresentation)', npc)
        self.assertIn('mountedSet ~= weaponSet', npc)

if __name__ == '__main__': unittest.main()
