"""M86: Monster module startup syntax and NPC peaceful vs combat presentation contracts."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class ActorAnimationStateTests(unittest.TestCase):
    def test_monster_special_connection_has_complete_luau_if(self):
        script = (ROOT / "src/server/monster/MonsterSpawnerService.luau").read_text(encoding="utf-8")
        self.assertIn('if choice.role == "special" then', script)
        self.assertNotIn('if choice.role == "special"\n', script)

    def test_npc_return_wait_is_passive_not_combat_idle(self):
        script = (ROOT / "src/server/npc/NpcAnimationService.luau").read_text(encoding="utf-8")
        ret = script.split('if returning then', 1)[1].split('elseif combatActive then', 1)[0]
        self.assertIn('Tracks.Stop(combatIdle)', ret)
        self.assertIn('idle:Start(false)', ret)
        self.assertNotIn('Tracks.Play(entity, combatIdle', ret)
        self.assertIn('idle:Start(true)', script)
        self.assertIn('Tracks.Play(entity, combatIdle, "combat_idle")', script.split('elseif combatActive then',1)[1])

    def test_specials_remain_blocked_until_home(self):
        script = (ROOT / "src/server/npc/NpcIdlePresentation.luau").read_text(encoding="utf-8")
        self.assertIn('function NpcIdlePresentation:Start(allowSpecials: boolean?)', script)
        self.assertIn('self.specialsAllowed = allowed', script)
        self.assertIn('if not self.active or not self.specialsAllowed or self.activeSpecial then', script)
        ai = (ROOT / "src/server/npc/NpcCombatAIService.luau").read_text(encoding="utf-8")
        home = ai.split('local function returnHome', 1)[1].split('local function attackCanConnect', 1)[0]
        self.assertLess(home.index('agent.root.CFrame = agent.home'), home.index('agent.presentation.SetReturnActive(false)'))


if __name__ == '__main__':
    unittest.main()
