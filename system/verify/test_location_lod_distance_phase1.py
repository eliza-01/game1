"""Location LOD phase 1 contracts: filename, publish name and safe Studio probe."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]

class LodDistancePhase1(unittest.TestCase):
    def test_lod1_published_name_is_slug_not_display_label(self):
        text = (ROOT/'system/control-center/services/location_lod_resource.py').read_text()
        self.assertIn("inspect_fbx(source_path, f'{slug}_lod1.fbx')", text)
        self.assertIn('publish_geometry(store.root, path, slug', text)
        common = (ROOT/'system/control-center/services/model_lod_common.py').read_text()
        self.assertIn('if source.name != expected_name:', common)
        self.assertIn("display_name=f'{slug}_lod1'", common)

    def test_policy_has_separate_hysteresis_states(self):
        text = (ROOT/'src/shared/world/LocationLodDistancePolicy.luau').read_text()
        for marker in ('function Policy.Resolve', 'config.hysteresis',
                       'LOD2', 'states[index]', 'cutoffs[index] + h',
                       'cutoffs[index - 1] - h'):
            self.assertIn(marker, text)

    def test_studio_probe_is_non_destructive_and_opt_in(self):
        text = (ROOT/'src/client/world/LocationLodStudioProbe.luau').read_text()
        self.assertIn('not RunService:IsStudio()', text)
        self.assertIn('CollectionService:GetTagged(TAG)', text)
        self.assertIn('Policy.WithHysteresis(spec.distances, profile.hysteresis)', text)
        self.assertIn('LocationLodStudioProbe', (ROOT/'src/lod-probe/init.client.luau').read_text())
        self.assertNotIn('LocationLodStudioProbe', (ROOT/'src/client/init.client.luau').read_text())
        project = (ROOT/'default.project.json').read_text()
        self.assertIn('Game1LodProbeClient', project)
        self.assertIn('src/lod-probe', project)
        self.assertIn('Game1LodProbeStatus', text)
        for unsafe in (':Destroy() --delete model', 'model:Destroy()', 'model:PivotTo(',
                       'model:ScaleTo(', 'LocalTransparencyModifier =', 'model.Parent = nil'):
            self.assertNotIn(unsafe, text)

if __name__ == '__main__': unittest.main()
