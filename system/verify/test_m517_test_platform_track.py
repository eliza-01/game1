"""Replacement of the M517 sprint-track contract by M539 full-scale GP zones."""
from pathlib import Path
import unittest
import math
ROOT = Path(__file__).resolve().parents[2]
def read(path): return (ROOT/path).read_text(encoding='utf8')

class TestZonePlatform(unittest.TestCase):
    def test_common_floor_and_bounds(self):
        arena=read('src/server/dev/GameplayTestArena.luau')
        service=read('src/server/dev/GameplayTestService.luau')
        layout=read('src/server/dev/GameplayTestLayout.luau')
        self.assertIn('Arena.BuildZonePlatform(folder, origin, s.spacing, size)', service)
        self.assertIn('local floorY = -CharacterConfig.RootAnchorOffset',layout)
        self.assertIn('local surface = point\n    if kind ~= "zone" then',arena)
        self.assertIn('deck(parent,platform.name,platform.top',arena)
        self.assertIn('math.ceil(width/1024)',arena)
        self.assertIn('math.ceil(depth/1024)',arena)
        self.assertIn('Arena.Warp(character, s.layout.slots[monster.id].visit)',service)
        self.assertIn('wall.CanCollide=false; wall.CanTouch=false; wall.CanQuery=false',arena)
        self.assertIn('wall.Transparency=0.82',arena)
        for width in (64,216,1536,2048,3000):
            n=math.ceil(width/1024); self.assertLessEqual(width/n,1024)
            self.assertAlmostEqual(n*(width/n),width)
    def test_speed_and_cleanup(self):
        service=read('src/server/dev/GameplayTestService.luau')
        self.assertIn('s.sampleConnection:Disconnect()',service)
        self.assertIn('Arena.Clear(s.population)',service)
        self.assertIn('s.folder:Destroy()',service)
        self.assertIn('Report.Sample(sample)',service)
        for p in ('src/shared/character/CharacterMovementConfig.luau','src/client/character/MovementController.luau','src/client/character/animation/CharacterAnimationController.luau','src/server/dev/GameplayTestService.luau'):
            self.assertNotIn('GameplayTestOnTrack',read(p))
            self.assertNotIn('TestTrackRunMultiplier',read(p))
