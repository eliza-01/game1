"""M244 contracts. Engine transform fidelity still requires a Studio Edit-mode test."""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / 'system/studio-plugin'
STATIC = ROOT / 'system/control-center/static'


class LocationSyncPlacementM244(unittest.TestCase):
    def source(self, path):
        return (ROOT / path).read_text(encoding='utf8')

    def test_shared_location_only_placement_policy_packaged(self):
        manifest = json.loads(self.source('system/studio-plugin/plugin.project.json'))
        self.assertEqual(manifest['tree']['modules']['StudioLocationPlacedGeometry']['$path'],
                         'modules/StudioLocationPlacedGeometry.luau')
        self.assertIn("'StudioLocationPlacedGeometry'",
                      self.source('system/studio-plugin/install.ps1'))
        helper = self.source('system/studio-plugin/modules/StudioLocationPlacedGeometry.luau')
        for call in ('target.Size.X / source.Size.X', 'target.Size.Y / source.Size.Y',
                     'target.Size.Z / source.Size.Z', 'part.CFrame = value.frame',
                     'source.PivotOffset = target.PivotOffset',
                     'source.CFrame ~= target.CFrame', 'validRatio(ratio.X)',
                     'verifyMultipart(previous, placed)', 'History.Provenance(placed, previous)'):
            self.assertIn(call, helper)
        self.assertIn('local function uniformRatio(', helper)
        self.assertIn('stage:ScaleTo(stage:GetScale() * newScale)', helper)
        self.assertIn('target.CFrame * source.CFrame:Inverse()', helper)
        self.assertIn('if oldScale == nil or newScale == nil then return nil end', helper)
        row_sync = self.source('system/studio-plugin/modules/DecoPlacedAssetSync.luau')
        registry_sync = self.source('system/studio-plugin/modules/StudioPlaceRegistrySync.luau')
        self.assertIn('Geometry.Align(stage,previousPublished,model)', row_sync)
        self.assertIn('Placement.PrepareSynced(stage,', row_sync)
        self.assertNotIn('Placement.PreparePlaced(stage,', row_sync)
        preparation = self.source('system/studio-plugin/modules/DecoAssetPreparation.luau')
        synced = preparation.split('function DecoAssetPreparation.PrepareSynced', 1)[1]
        self.assertIn('MeshPhysics.ApplyLocationModel', synced)
        self.assertNotIn('Anchored = false', synced)
        self.assertIn('Geometry.Align(stage,previous,root)', registry_sync)
        self.assertNotIn('stage:ScaleTo(model:GetScale())', row_sync)
        # This policy MUST NOT change shared Real Estate geometry transactions.
        self.assertNotIn('StudioLocationPlacedGeometry',
            self.source('system/studio-plugin/modules/StudioRealEstatePlacedVisualSync.luau'))

    def test_wrong_slug_is_not_automatic_foreign_ownership(self):
        inventory = self.source('system/studio-plugin/modules/StudioPlaceRegistryInventory.luau')
        self.assertIn('History.MatchesInventory(root,publication)', inventory)
        self.assertIn('ambiguous=not eligible or provenForeignClaim', inventory)
        self.assertIn('Устаревшая метка slug:', inventory)
        self.assertIn('canSync=eligible and not foreignClaim', inventory)
        self.assertNotIn('Model явно принадлежит другому Location Asset', inventory)
        repair = self.source('system/studio-plugin/modules/StudioPlaceRegistryRepair.luau')
        self.assertIn('root:SetAttribute("Game1DecoAssetSlug",ref.entry.slug)', repair)

    def test_find_report_survives_replace_and_rescans(self):
        source = self.source('system/control-center/static/location-asset-workflow.js')
        self.assertIn('async function refreshSyncReport()', source)
        self.assertIn('state.scanStale=true', source)
        self.assertIn('await refreshSyncReport();', source)
        self.assertNotIn('state.scan=null; // single-use token, including on failure', source)
        node = shutil.which('node')
        if node:
            run = subprocess.run([node, str(ROOT/'system/verify/location_model_group_sync_m239.js')],
                                 capture_output=True,text=True,timeout=20)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)


if __name__ == '__main__':
    unittest.main()
