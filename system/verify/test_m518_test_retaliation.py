"""M518: zone monsters participate in the normal retaliation pipeline."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
def read(path):
    return (ROOT / path).read_text(encoding='utf8')

class TestRetaliation(unittest.TestCase):
    def test_zone_uses_mobile_agent(self):
        lifecycle = read('src/server/monster/MonsterAgentLifecycle.luau')
        spawner = read('src/server/monster/MonsterSpawnerService.luau')
        initial = read('src/server/monster/MonsterInitialAttributes.luau')
        self.assertNotIn('if model:GetAttribute("GameplayTestKind") == "zone" then return end', lifecycle)
        self.assertNotIn('navigationRoot.Anchored = true', spawner)
        self.assertIn('if not record.testOwner then wanderController:Start', spawner)
        self.assertIn('if balance then balance.aggressive == true', initial)
        self.assertIn('if record.testKind ~= "zone" then', initial)
        ai = read('src/server/monster/MonsterAIService.luau')
        self.assertIn('if not aggressive(agent) and not agent.retaliating and not agent.returning', ai)
        self.assertIn('DamageSignals.Event:Connect(onDamaged)', ai)
        self.assertIn('agent.retaliating = true', ai)

    def test_owner_only_damage_both_directions(self):
        policy = read('src/server/dev/GameplayTestIsolation.luau')
        self.assertIn('if source == nil or source ~= destination or not attacker then return false end', policy)
        self.assertIn('(sourceKind == "player" and (targetKind == "zone" or targetKind == "group"))', policy)
        self.assertIn('((sourceKind == "zone" or sourceKind == "group") and targetKind == "player")', policy)
        self.assertIn('sourceKind == "group" and attacker:GetAttribute("GameplayTestArmed") ~= true', policy)
        self.assertIn('targetKind == "group" and target:GetAttribute("GameplayTestArmed") ~= true', policy)
        self.assertIn('Isolation.Allows(attacker, target)', read('src/server/combat/DamageService.luau'))

    def test_lost_target_returns_home(self):
        ai = read('src/server/monster/MonsterAIService.luau')
        self.assertIn('if agent.target then beginReturn(agent); return end', ai)
        branch = ai.split('        updateTarget(agent, now)\n', 1)[1].split('        local target = agent.target', 1)[0]
        self.assertIn('if agent.returning then\n            updateReturn(agent)\n            continue\n', branch)
        self.assertIn('navigateTo(agent, home, runSpeedStuds(agent))', ai)
        self.assertIn('testNoRespawn = kind == "group"', read('src/server/dev/GameplayTestArena.luau'))

if __name__ == '__main__':
    unittest.main()
