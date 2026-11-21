"""M407: already-current placed rigs are not replaced to repair stale Model stamps.

Structural guard only: Roblox Instance/AssetService execution must still be checked
in Studio on a backup Place. Keep this guard focused on the actual failure path.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = (ROOT / 'system/studio-plugin/modules/DecoPlacedAssetSync.luau')


class M407CurrentRigSync(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SRC.read_text(encoding='utf-8')
        cls.refresh = cls.source.split('function DecoPlacedAssetSync.RefreshIds(', 1)[1]

    def test_current_publication_requires_full_evidence(self):
        fn = self.source.split('local function matchesCurrentPublishedRig(', 1)[1].split(
            '\n-- Read-only eligibility check', 1)[0]
        self.assertIn('Carrier.Diagnose(model, row.rigManifest, row.legacyStaticPublication)', fn)
        self.assertIn('History.MatchesInventory(model, History.Describe(', fn)
        self.assertIn('History.VerifyChildren, published, rigChildren(model)', fn)
        self.assertIn('Geometry.Align, probe, reference, model', fn)
        self.assertIn('source.Size - target.Size', fn)
        self.assertIn('source.CFrame.Position - target.CFrame.Position', fn)
        self.assertIn('authoredBones[item.Name]', fn)
        self.assertIn('probe:Destroy()', fn)
        self.assertIn('reference:Destroy()', fn)
        self.assertNotIn('SetAttribute(', fn)
        self.assertNotIn('RigSwap.Commit(', fn)

    def test_metadata_only_path_does_not_commit_or_fake_model_change(self):
        refresh = self.refresh
        self.assertIn('metadataCurrent = matchesCurrentPublishedRig(model, published :: Model, row)', refresh)
        self.assertIn('if metadataCurrent then\n                    geometry = false', refresh)
        self.assertIn('changeRef = (geometry or metadataCurrent) and oldRef ~= modelId', refresh)
        self.assertIn('geometry = geometry, metadataCurrent = metadataCurrent', refresh)
        self.assertIn('if item.swap or item.metadataCurrent then', refresh)
        self.assertIn('if item.swap then\n                RigSwap.Commit(item.swap)', refresh)
        self.assertIn('if geometry then add("model", previousModelId, modelId, 1)', refresh)
        self.assertIn('add("model_reference", oldId, modelId, 1)', refresh)
        self.assertIn('elseif Visual.Apply(change.part,row)', refresh)
        self.assertIn('if not geometry then', refresh)
        self.assertLess(refresh.index('metadataCurrent = matchesCurrentPublishedRig'),
                        refresh.index('RigSwap.Prepare(model, previousChildren, rigChildren(stage)'))
        self.assertLess(refresh.index('RigSwap.Commit(item.swap)'),
                        refresh.index('model:SetAttribute("Game1DecoPublishedModelAssetId", modelId)'))

    def test_genuinely_old_rigs_still_require_historical_publication(self):
        refresh = self.refresh
        self.assertIn('History.MatchesInventory(model,entry)', refresh)
        self.assertIn('ambiguous historical Model version', refresh)
        self.assertIn('historical Model evidence missing for', refresh)
        self.assertIn('placed Mesh IDs=', refresh)
        self.assertIn('stamped Model ID=', refresh)
        self.assertIn('loader:loadHistoricalRigForComparison(', refresh)
        self.assertIn('History.VerifyChildren(previousPublished,previousChildren)', refresh)
        self.assertIn('BoneEffects.CopyToIncoming(previousChildren, rigChildren(stage))', refresh)
        self.assertIn('RigSwap.Prepare(model, previousChildren, rigChildren(stage)', refresh)
        self.assertIn('RigSwap.Rollback(item.swap)', refresh)
        self.assertIn('model:SetAttribute("Game1DecoPublishedModelAssetId", item.oldPublishedId)', refresh)
        self.assertIn('model:SetAttribute(HISTORY, item.oldHistory)', refresh)

    def test_owner_scope_and_find_token_not_bypassed(self):
        manager = (ROOT / 'system/studio-plugin/modules/DecoManager.luau').read_text(encoding='utf-8')
        self.assertIn('self.meshSyncPreview=nil -- one-time token', manager)
        self.assertIn('scanned.partByKey[key]', manager)
        self.assertIn('Ownership.ForPart(workspace, part, slug, row.aliases)', self.source)
        self.assertIn('selected MeshPart is outside the SHA-bound physics report', self.source)
        self.assertIn('if Ownership.HasNestedPlacements(model) then', self.source)


if __name__ == '__main__':
    unittest.main()
