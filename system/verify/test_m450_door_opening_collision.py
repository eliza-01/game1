"""M450 · Door collision contract; runtime physics still requires Studio Play."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]

def source(relative):
    return (ROOT / relative).read_text(encoding='utf-8')

class HouseDoorCollisionM450(unittest.TestCase):
    def test_snapshot_tracks_authored_values_and_restores_only_live_parts(self):
        code = source('src/server/world/HouseDoorCollision.luau')
        self.assertIn('snapshot[descendant] = descendant.CanCollide', code)
        self.assertIn('descendant.CanCollide = false', code)
        self.assertIn('if part.Parent then', code)
        self.assertIn('part.CanCollide = wasCollidable', code)
        self.assertIn('return table.freeze(Collision)', code)
        self.assertNotIn('part.CanCollide = true', code)

    def test_only_opening_suspends_and_cleanup_restores(self):
        door = source('src/server/world/HouseDoorService.luau')
        self.assertIn('local Collision = require(script.Parent:WaitForChild("HouseDoorCollision"))', door)
        opening = door.split('    -- Opening: avoid pushing', 1)[1].split('    door:SetAttribute("Game1DoorMoving", true)', 1)[0]
        self.assertIn('if not open then', opening)
        self.assertIn('Collision.Suspend(door)', opening)
        self.assertNotIn('Collision.Suspend(door)', door.split('local function clearAnimation', 1)[0])
        self.assertEqual(door.count('Collision.Suspend(door)'), 1)
        cleanup = door.split('local function clearAnimation(door: Model)', 1)[1].split('function Doors.Toggle', 1)[0]
        self.assertIn('Collision.Restore(entry.collisionSnapshot)', cleanup)
        self.assertIn('door:SetAttribute("Game1DoorMoving", false)', cleanup)
        self.assertLess(cleanup.index('Collision.Restore(entry.collisionSnapshot)'), cleanup.index('door:SetAttribute("Game1DoorMoving", false)'))
        self.assertIn('tween.Completed:Connect(function()', door)
        self.assertIn('clearAnimation(door)', door.split('tween.Completed:Connect(function()',1)[1])
        self.assertIn('if active[door] then return false', door)
        self.assertIn('for door in active do', door)

    def test_no_house_wide_collision_changes_and_docs(self):
        door = source('src/server/world/HouseDoorService.luau')
        collision = source('src/server/world/HouseDoorCollision.luau')
        self.assertIn('door:GetDescendants()', collision)
        self.assertNotIn('house:GetDescendants()', door + collision)
        self.assertIn('При ОТКРЫВАНИИ', source('system/control-center/mechanics/house.py'))
        self.assertIn('закрывание', source('docs/spec/CURRENT_PROJECT_SPEC_RU.md'))

if __name__ == '__main__':
    unittest.main()
