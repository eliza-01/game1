"""Target lock wiring; Studio smoke exercises real Vector3/LOS checks."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def source(path):
    return (ROOT / path).read_text(encoding='utf8')


class MonsterTargetLock(unittest.TestCase):
    def test_normal_and_targeted_cast_use_shared_rigid_goal(self):
        tracker = source('src/server/actor/ActorFacingTracker.luau')
        normal = source('src/server/monster/MonsterAttackExecutor.luau')
        special = source('src/server/monster/MonsterSkillCast.luau')
        npc = source('src/server/npc/NpcCombatAIService.luau')
        self.assertIn('rigid: boolean?', tracker)
        self.assertIn('align.RigidityEnabled = rigid == true', tracker)
        self.assertIn('updateGoal(entry, targetRoot)', tracker)
        self.assertIn('updateGoal(active[model], targetRoot)', tracker)
        self.assertEqual(tracker.count('RunService.Heartbeat:Connect(step)'), 1)
        self.assertNotIn('root.CFrame =', tracker)
        self.assertIn('Facing.Track(agent.model, agent.root, agent.humanoid, target, rootOf, true)', normal)
        self.assertIn('Facing.Track(model,agent.root,agent.humanoid,target,Target.RootOf,true)', special)
        self.assertIn('Facing.Track(agent.model, agent.root, agent.humanoid, target, Queries.Root)', npc)
        self.assertIn('Facing.Stop(agent.model)', normal)
        self.assertIn('Facing.Stop(model)', special)

    def test_normal_hit_retains_live_checks_and_single_damage_owner(self):
        policy = source('src/server/monster/MonsterTargetPolicy.luau')
        hit = policy.split('local function attackStillConnects', 1)[1].split('\nend', 1)[0]
        self.assertNotIn('LookVector', hit)
        self.assertNotIn('ATTACK_ARC_DEGREES', policy)
        self.assertIn('if not withinAttackRange(agent, target) then return false end', hit)
        self.assertIn('return hasLineOfSight(agent, target)', hit)
        distance = policy.split('local function withinAttackRange', 1)[1].split('\nend', 1)[0]
        for check in ('not targetIsValid(target)', 'not allowsTarget(agent, target)', 'delta.Magnitude > attackRadius(agent)', '> VERTICAL_TOLERANCE'):
            self.assertIn(check, distance)
        normal = source('src/server/monster/MonsterAttackExecutor.luau')
        hit = normal.split('task.delay(hitTime, function()', 1)[1].split('task.delay(duration, function()', 1)[0]
        self.assertIn('agent.attackSerial ~= serial', hit)
        self.assertIn('agent.target ~= target', hit)
        self.assertLess(hit.index('TargetPolicy.AttackStillConnects'), hit.index('DamageService.Apply'))
        self.assertEqual(hit.count('DamageService.Apply('), 1)

    def test_no_unused_shadow_facing_state(self):
        for name in ('MonsterAIService', 'MonsterAttackExecutor', 'MonsterAgentLifecycle'):
            self.assertNotIn('agent.facing', source(f'src/server/monster/{name}.luau'))
            self.assertNotIn('FaceDirection', source(f'src/server/monster/{name}.luau'))


if __name__ == '__main__':
    unittest.main()
