"""Safety contract: exact skinned visual inventory despite retired COL and no unsafe sync."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
HISTORY = (ROOT/'system/studio-plugin/modules/StudioPublishedMeshHistory.luau').read_text(encoding='utf-8')
SCANNER = (ROOT/'system/studio-plugin/modules/StudioPlaceRegistryInventory.luau').read_text(encoding='utf-8')

class TestRetiredSkinnedSnapshotDiagnostics(unittest.TestCase):
    def test_strict_nonvisual_exception_requires_stamped_owned_model(self):
        self.assertIn('function Inventory.MatchesRetiredSkinnedPhysics', HISTORY)
        for required in ('Game1DecoInstanceId', 'Game1DecoAssetSlug',
                         'Game1DecoPublishedModelAssetId', 'Ownership.HasNestedPlacements',
                         'manifest.rigKind ~= "skinned"', 'manifest.carrierName ~= "rig_carrier"',
                         'missingNonvisual == 1', 'if carriers ~= 1 then return false end'):
            self.assertIn(required, HISTORY)
        self.assertIn('History.MatchesRetiredSkinnedPhysics(candidate, version, entry)', SCANNER)

    def test_unverified_stamped_model_never_authorizes_sync_or_repair(self):
        self.assertIn('local unverified=if eligible and not root', SCANNER)
        self.assertIn('local placement: Instance = root or unverified or part', SCANNER)
        self.assertIn('ambiguous=not eligible or provenForeignClaim or unverified~=nil', SCANNER)
        self.assertIn('hasModel=root~=nil or unverified~=nil', SCANNER)
        self.assertIn('and root~=nil and assigned~=""', SCANNER)
        self.assertIn('canRepair=eligible and structuralState == "current" and root~=nil', SCANNER)

if __name__=='__main__':
    unittest.main()
