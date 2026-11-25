"""Contracts for the shared platform and temporary sprint zone."""
from pathlib import Path
import unittest
import math

ROOT = Path(__file__).resolve().parents[2]
def read(path):
    return (ROOT / path).read_text(encoding='utf8')

class TestPlatformTrack(unittest.TestCase):
    def test_common_floor_and_track(self):
        arena = read('src/server/dev/GameplayTestArena.luau')
        service = read('src/server/dev/GameplayTestService.luau')
        layout = read('src/server/dev/GameplayTestLayout.luau')
        self.assertIn('Arena.BuildLinePlatform(folder, origin, s.spacing, size)', service)
        self.assertIn('local floorY = -CharacterConfig.RootAnchorOffset', layout)
        self.assertIn('local surface = point\n    if kind ~= "line" then', arena)
        self.assertIn('deck(parent, "MonsterPlatform", layout.platformTop', arena)
        self.assertIn('deck(parent, track.name, track.top', arena)
        self.assertIn('math.ceil(width / 1024)', arena)
        self.assertIn('Arena.Warp(character, s.layout.slots[monster.id].visit)', service)
        self.assertIn('math.ceil(maxLevel / 2)', layout)
        for count in (1, 35):
            for sx, sy, sz in ((2, 4, 2), (5, 8, 6), (20, 30, 20)):
                spacing = math.ceil(2 * (40 + math.sqrt(sx*sx + sy*sy + sz*sz)) + 4)
                margin = max(12, max(sx,sz)/2+4, math.ceil(12*(max(sx, sz)+2)/(2*math.pi))+4)
                cols = math.ceil(count / 2)
                width = (cols-1)*spacing + 2*margin
                center = (cols-1)*spacing/2
                self.assertTrue(all(abs(i*spacing-center)+sx/2 <= width/2 for i in range(cols)))
                n = math.ceil(width/1024)
                self.assertLessEqual(width/n, 1024)
                self.assertAlmostEqual(n*(width/n), width)

    def test_speed_and_cleanup(self):
        arena = read('src/server/dev/GameplayTestArena.luau')
        service = read('src/server/dev/GameplayTestService.luau')
        config = read('src/shared/character/CharacterMovementConfig.luau')
        movement = read('src/client/character/MovementController.luau')
        animation = read('src/client/character/animation/CharacterAnimationController.luau')
        self.assertIn('trackTop:PointToObjectSpace(feet)', arena)
        self.assertIn('math.abs(point.Z) <= trackSize.Z / 2', arena)
        self.assertIn('point.Y >= -0.75 and point.Y <= 4', arena)
        self.assertIn('character:GetAttribute("Game1GameplayTestOwner") == s.player.UserId', service)
        self.assertIn('s.trackConnection:Disconnect()', service)
        self.assertIn('character:SetAttribute("GameplayTestOnTrack", nil)', service)
        self.assertNotIn('SetAttribute("RunSpeed"', service)
        self.assertIn('if movementMode == "Run"', config)
        self.assertIn('and model:GetAttribute("GameplayTestOnTrack") == true then\n        return 3', config)
        self.assertIn('TestTrackRunMultiplier(targetCharacter, movementMode)', movement)
        self.assertIn('TestTrackRunMultiplier(character, nextMode)', movement)
        attack = movement.split('local function applyMovementMode', 1)[1].split('else\n\t\t\tcontrollerManager.BaseMoveSpeed', 1)[0]
        self.assertNotIn('TestTrackRunMultiplier', attack)
        self.assertIn('percent *= CharacterMovementConfig.TestTrackRunMultiplier(character, "Run")', animation)
        self.assertIn('"GameplayTestOnTrack" }', animation)

if __name__ == '__main__':
    unittest.main()
