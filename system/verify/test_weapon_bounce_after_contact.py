"""Source-level contracts for post-contact bounce suppression (Studio physics test still required)."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


class WeaponBounceAfterContactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.attack = read('src/server/combat/AttackService.luau')
        cls.registry = read('src/server/combat/HostilePursuitRegistry.luau')
        cls.monster = read('src/server/monster/MonsterAIService.luau')
        cls.monster_state = read('src/server/monster/MonsterCombatState.luau')
        cls.monster_lifecycle = read('src/server/monster/MonsterAgentLifecycle.luau')
        cls.npc = read('src/server/npc/NpcCombatAIService.luau')
        cls.collision = read('src/server/combat/WeaponEnvironmentCollision.luau')
        cls.session = read('src/server/combat/AttackSessionStore.luau')

    def test_collision_query_is_unconditional_and_precedes_bounce_rule(self):
        sweep = self.attack.split('local function applyAnimatedWeaponSweep', 1)[1].split('local function clearAttackState', 1)[0]
        self.assertIn('local environmentContact = WeaponEnvironmentCollision.Query(previousVolume, volume)', sweep)
        self.assertIn('if environmentContact then', sweep)
        self.assertLess(sweep.index('WeaponEnvironmentCollision.Query(previousVolume, volume)'),
                        sweep.index('HostilePursuitRegistry.Count(character)'))
        self.assertLess(sweep.index('HostilePursuitRegistry.Count(character)'),
                        sweep.index('triggerWeaponBounce('))
        self.assertIn('if character:GetAttribute("InCombat") == true or pursuerCount > 0 then', sweep)
        self.assertIn('else\n                    local bounced = triggerWeaponBounce(', sweep)
        self.assertLess(sweep.index('triggerWeaponBounce('), sweep.index('hitCount += applyDamageInVolume('))
        self.assertNotIn('WeaponEnvironmentBouncePolicy', self.attack)

    def test_damage_window_and_sweep_have_not_been_rewritten(self):
        self.assertIn('local damageWindow = CharacterAttackWindow.Resolve(timing)', self.attack)
        self.assertIn('AttackSessionStore.Begin(player, character, serial, clientAttackId, now + attackDuration, damageWindow)', self.attack)
        self.assertIn('damageWindow = damageWindow', self.session)
        self.assertIn('WeaponAttackVolume.Build(root.Position, sampledBoxCFrame, boxSize, attackRange, weaponBoneBoxLocalPosition)', self.attack)
        self.assertIn('hitCount += applyDamageInVolume(', self.attack)
        self.assertIn('local environmentContact = WeaponEnvironmentCollision.Query(previousVolume, volume)', self.attack)

    def test_registry_tracks_multiple_hostiles_and_cleans_on_death(self):
        self.assertIn('pursuerCount[target] = (pursuerCount[target] or 0) + 1', self.registry)
        self.assertIn('local remaining = (pursuerCount[entry.target] or 1) - 1', self.registry)
        self.assertIn('targetDestroying: RBXScriptConnection', self.registry)
        self.assertIn('targetLifeStateChanged: RBXScriptConnection', self.registry)
        self.assertIn('hostile.Destroying:Connect(', self.registry)
        self.assertIn('hostile:GetAttributeChangedSignal("LifeState")', self.registry)
        self.assertIn('function HostilePursuitRegistry.Count(character: Model): number', self.registry)

    def test_monster_npc_publish_target_transitions(self):
        self.assertIn('HostilePursuitRegistry.SetTarget(agent.model, target)', self.monster_state)
        self.assertIn('CombatState.Enter(agent, target)', self.monster)
        self.assertIn('HostilePursuitRegistry.SetTarget(agent.model, target)', self.npc)
        self.assertIn('HostilePursuitRegistry.Clear(agent.model)', self.monster_state)
        self.assertGreaterEqual((self.monster + self.monster_lifecycle).count('CombatState.ClearTarget(agent)'), 2)
        self.assertGreaterEqual(self.monster_lifecycle.count('CombatState.ClearTarget(agent)'), 2)
        self.assertIn('CombatState.FinishExit(agent)', self.monster)
        self.assertGreaterEqual(self.npc.count('HostilePursuitRegistry.Clear('), 3)

    def test_environment_detection_implementation_unchanged(self):
        self.assertIn('Workspace:Blockcast(', self.collision)
        self.assertIn('Workspace:GetPartsInPart(', self.collision)
        self.assertIn('EnvironmentAssetService.ResolvePart(part)', self.collision)


if __name__ == '__main__':
    unittest.main()
