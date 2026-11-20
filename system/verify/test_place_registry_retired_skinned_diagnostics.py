"""M398: skinned Place provenance is exact, not an exception for retired COL."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
HISTORY = (ROOT/'system/studio-plugin/modules/StudioPublishedMeshHistory.luau').read_text(encoding='utf-8')
SCANNER = (ROOT/'system/studio-plugin/modules/StudioPlaceRegistryInventory.luau').read_text(encoding='utf-8')
PUBLISHED = (ROOT/'system/studio-plugin/modules/StudioLocationPublishedGeometry.luau').read_text(encoding='utf-8')


class TestSkinnedSnapshotDiagnostics(unittest.TestCase):
    def test_retired_skinned_collision_exception_removed(self):
        # New current FULL publications must contain the actual complete rig;
        # immutability of old Roblox IDs cannot authorize silently missing parts.
        self.assertNotIn('MatchesRetiredSkinnedPhysics', HISTORY + SCANNER + PUBLISHED)
        self.assertIn('function Inventory.MatchesInventory', HISTORY)
        self.assertIn('History.MatchesInventory(candidate, version)', SCANNER)
        self.assertIn('History.MatchesInventory(root, version)', PUBLISHED)

    def test_unverified_stamped_model_never_authorizes_sync_or_repair(self):
        self.assertIn('local unverified=if eligible and not root', SCANNER)
        self.assertIn('local placement: Instance = root or unverified or part', SCANNER)
        self.assertIn('ambiguous=not eligible or provenForeignClaim or unverified~=nil', SCANNER)
        self.assertIn('hasModel=root~=nil or unverified~=nil', SCANNER)
        self.assertIn('and root~=nil and assigned~=""', SCANNER)
        self.assertIn('canRepair=eligible and structuralState == "current" and root~=nil', SCANNER)


if __name__ == '__main__':
    unittest.main()
