from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]

class NpcGroundComparisonM421(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = (ROOT / "src/server/dev/NpcGroundComparisonService.luau").read_text(encoding="utf-8")
        cls.catalog = (ROOT / "src/server/bootstrap/ServiceCatalog.luau").read_text(encoding="utf-8")

    def test_is_studio_only_read_only_and_noncritical(self):
        self.assertIn('not RunService:IsStudio()', self.src)
        self.assertIn('critical = false, dependsOn = {"NpcSpawnerService"}', self.catalog)
        self.assertIn('require(dev:WaitForChild("NpcGroundComparisonService")).Start()',self.catalog)
        for mutation in ('root.CFrame =', 'root.Anchored =', 'SetAttribute(', ':PivotTo(', ':MoveTo(', ':Destroy()'):
            self.assertNotIn(mutation, self.src)

    def test_samples_both_guards_across_combat_and_by_player(self):
        for token in ('guard_01_711887','guard_02_520666','kitiket322322',
                      'NpcSlug','NpcAIState','NpcAttackPhase','NpcAnimationState',
                      'HumanoidRootPart','TransformedWorldCFrame','GetPlayingAnimationTracks',
                      'rootAboveGround','visualBottomAboveGround','spineAboveRoot',
                      'rootYFromSpawn','rootVerticalSpeed','rootCollisionGroup'):
            self.assertIn(token,self.src)

    def test_bounded_and_reuses_server_output(self):
        self.assertIn('MAX_SECONDS = 240',self.src)
        self.assertIn('SAMPLE_STEP = 0.2',self.src)
        self.assertIn('connection:Disconnect()',self.src)
        self.assertIn('[game1][npc-ground]',self.src)
        self.assertNotIn('RemoteEvent',self.src)

if __name__ == '__main__': unittest.main()
