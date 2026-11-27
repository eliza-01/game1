"""M616: exact XZ broad phase in Lua + protected M615 policies."""
from pathlib import Path
import hashlib
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]

def read(path):
    return (ROOT / path).read_text(encoding='utf-8')

class PlayerSpatialM616(unittest.TestCase):
    def test_grid_and_batch_behavior(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua:
            self.skipTest('Lua CLI unavailable')
        subprocess.run([lua, 'system/verify/player_spatial_m616.lua'], cwd=ROOT, check=True, timeout=15)

    def test_target_policies_unchanged_except_candidate_source(self):
        for path, start, replacement, expected in (
            ('src/server/monster/MonsterTargetPolicy.luau', 'local function navigationRootOf',
             'PlayerSpatialIndex.Query(agent.root.Position, closestDistance)', 'd3b55a1ca15c8387353f817149b636388a3b34154db9a40d24c3d85644a1a795'),
            ('src/server/actor/ActorCombatTargeting.luau', 'function ActorCombatTargeting.Valid',
             'PlayerSpatialIndex.Query(position, radius)', 'a60b5d16a943b7a120667d46f6c2bee881fc897590e6ebef6235443be44b535c'),
        ):
            source = read(path)
            self.assertNotIn('Players:GetPlayers()', source)
            self.assertIn('ActorTargetRoot.Get', source)
            body = source[source.index(start):].replace(replacement, 'Players:GetPlayers()')
            self.assertEqual(hashlib.sha256(body.strip().encode()).hexdigest(), expected)

    def test_scheduler_scope_and_shared_lifecycle(self):
        scheduler = read('src/server/actor/ActorAIScheduler.luau')
        self.assertEqual(scheduler.count('RunService.Heartbeat:Connect'), 1)
        self.assertLess(scheduler.index('PlayerSpatialIndex.BeginBatch()'), scheduler.index('pcall(queue.Pump'))
        self.assertLess(scheduler.index('pcall(queue.Pump'), scheduler.index('PlayerSpatialIndex.EndBatch()'))
        service = read('src/server/actor/PlayerSpatialIndex.luau')
        self.assertEqual(service.count('Players:GetPlayers()'), 1)
        self.assertNotIn('Heartbeat', service.split('local Players', 1)[1])
        self.assertIn('Players.PlayerAdded:Connect(Index.Invalidate)', service)
        self.assertIn('Players.PlayerRemoving:Connect(Index.Invalidate)', service)
        for path, statement in (
            ('character/CharacterService', 'player.Character = nil'),
            ('character/CharacterService', 'player.Character = character'),
            ('dev/GameplayTestArena', 'character:PivotTo(frame)'),
            ('world/HouseElevatorService', 'character:PivotTo(targetFrame)'),
            ('world/HouseSocketService', 'character:PivotTo(targetFrame)'),
        ):
            self.assertRegex(read('src/server/' + path + '.luau'), statement.replace('(', r'\(').replace(')', r'\)') + r'\n\s+PlayerSpatialIndex\.Invalidate\(\)')

    def test_runtime_and_mechanics(self):
        self.assertIn('"$path": "src/server"', read('default.project.json'))
        catalog = read('system/control-center/mechanics/catalog.py')
        for key in ('player-spatial-index', 'player-spatial-grid', 'actor-target-root'):
            self.assertIn(key, catalog)
            for name in ('monster', 'npc'):
                self.assertIn(key, read('system/control-center/mechanics/' + name + '.py'))
        # NPC is retaliation-only in M615; do not turn on proactive Aggro.
        self.assertNotIn('Queries.ClosestPlayer(', read('src/server/npc/NpcCombatAIService.luau'))
