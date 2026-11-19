"""M375: published house revisions can replace managed placed geometry by type.

These are source-contract and persisted-data checks; live Studio geometry requires
an actual Studio Edit/Play smoke test, not a mocked Roblox scene.
"""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
STUDIO = ROOT / 'system' / 'studio-plugin' / 'modules'
sys.path.insert(0, str(ROOT / 'system/control-center'))
from real_estate.placement import RealEstatePlacementStore
from sqlite_connection import connect


def source(module):
    return (STUDIO / (module + '.luau')).read_text(encoding='utf-8')


class HouseRepublicationPlacedSync(unittest.TestCase):
    def test_complete_sync_is_not_keyed_by_old_meshpart_names(self):
        sync = source('StudioRealEstatePlacedVisualSync')
        self.assertIn('managedChildren(root, true)', sync)
        self.assertIn('managedChildren(template, true)', sync)
        self.assertIn('RigSwap.Prepare(root, oldRigs, newRigs', sync)
        self.assertIn('RigSwap.Commit(plan)', sync)
        self.assertNotIn('root:FindFirstChild(source.Name)', sync)
        self.assertNotIn('if not old or not old:IsA("Model")', sync)
        self.assertNotIn('root:Destroy()', sync)
        self.assertIn('Game1RealEstateManagedRig', sync)
        self.assertIn('FindFirstChildWhichIsA("MeshPart", true)', sync)
        self.assertIn('root.Name ~= slug', sync)
        self.assertIn('no verified managed visual rigs', sync)
        self.assertIn('update rolled back', sync)

    def test_original_plot_pivot_and_scale_are_not_discarded(self):
        sync = source('StudioRealEstatePlacedVisualSync')
        swap = source('StudioManagedRigSwap')
        self.assertIn('placed:GetPivot()', sync)
        self.assertIn('placed:GetScale() / templateScale', sync)
        self.assertIn('candidate:ScaleTo(source:GetScale() * ratio)', sync)
        self.assertIn('preferredPrimary = preferredPrimary(newRigs)', sync)
        self.assertIn('plan.newPrimary.PivotOffset = plan.newPrimary.CFrame:ToObjectSpace(plan.pivot)', swap)
        self.assertIn('if not sameFrame(actualPivot, plan.pivot)', swap)
        for mutator in ('root:PivotTo(', 'root:ScaleTo(', 'root:Destroy(', 'root:SetAttribute("Game1PlotIndex",',
                        'root:SetAttribute("Game1PlacementRevision",'):
            self.assertNotIn(mutator, sync)

    def test_template_uses_canonical_carrier_and_managed_assemblies(self):
        studio = source('StudioRealEstateModel')
        self.assertIn('tonumber(metadata.houseAuthoringVersion) == 4', studio)
        self.assertIn('rootCarrier, carrierInspection = StudioRealEstateRigValidation.Verify(', studio)
        self.assertIn('wrapper.PrimaryPart = rootCarrier', studio)
        self.assertIn('static.Name = "StaticAssembly"', studio)
        self.assertIn('SkinConnection.Connect(static, rootCarrier', studio)
        self.assertIn('entry.rig:SetAttribute("Game1RealEstateManagedRig", true)', studio)
        self.assertIn('assembly:SetAttribute("Game1RealEstateManagedRig", true)', studio)
        self.assertIn('StudioRealEstatePlacedVisualSync.Update(wrapper, slug, placedTargets)', studio)
        self.assertNotIn('PartPlacement.AlignOrigin(', studio)
        self.assertIn("'houseAuthoringVersion': 4", (ROOT / 'system/control-center/real_estate/studio_sync.py').read_text(encoding='utf-8'))

    def test_plugin_install_catches_old_real_estate_module(self):
        installer = (ROOT / 'system/studio-plugin/install.ps1').read_text(encoding='utf-8')
        self.assertIn("'Game1RealEstateManagedRig'", installer)
        self.assertIn("'independent-authored-rig-carrier'", installer)
        self.assertIn("'StudioRealEstatePlacedVisualSync'", installer)

    def test_removed_house_type_keeps_saved_placements(self):
        class Registry:
            def get(self, slug):
                return None
        def cf(x):
            return [x, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.control-center').mkdir()
            storage = RealEstatePlacementStore(root, Registry())
            row = storage.bind('house_level5_01', 39, {
                'schemaVersion': 2, 'houseSlug': 'house_level5_01', 'plotIndex': 39,
                'plotVolume': 'plot_39_volume', 'worldCFrame': cf(250),
                'plotCFrame': cf(230), 'localCFrame': cf(20),
                'houseAnchorLocalCFrame': cf(0), 'houseAnchorWorldCFrame': cf(250),
                'scale': 1.5,
            })
            self.assertEqual(RealEstatePlacementStore(root, Registry()).get('house_level5_01', 39), row)


if __name__ == '__main__':
    unittest.main()
