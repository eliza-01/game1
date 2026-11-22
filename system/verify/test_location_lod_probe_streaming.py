"""The Studio LOD probe must survive deferred replication of tagged Models."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "src/client/world/LocationLodStudioProbe.luau"


class LodProbeStreaming(unittest.TestCase):
    def test_tagged_models_are_registered_before_geometry_is_required(self):
        source = PROBE.read_text()
        self.assertIn('monitored[model] = record', source)
        self.assertIn('if refreshGeometry(model, record) then', source)
        self.assertLess(source.index('monitored[model] = record'),
                        source.index('if refreshGeometry(model, record) then'))
        self.assertNotIn('Tagged Model has no BasePart:', source)

    def test_missing_and_streamed_out_meshparts_are_rechecked(self):
        source = PROBE.read_text()
        self.assertIn('local function refreshGeometry(model, record)', source)
        self.assertIn('previous:IsDescendantOf(model)', source)
        self.assertIn('model:FindFirstChildWhichIsA("BasePart", true)', source)
        self.assertIn('elseif refreshGeometry(model, record) then', source)
        self.assertIn('record.gui.Adornee = current', source)
        self.assertIn('Geometry streamed out:', source)

    def test_status_distinguishes_tag_from_loaded_geometry(self):
        source = PROBE.read_text()
        self.assertIn('0 tagged Models in Workspace', source)
        self.assertIn('0 with geometry', source)
        self.assertIn('%d tagged | %d ready', source)
        self.assertIn('Policy.WithHysteresis(spec.distances, profile.hysteresis)', source)

    def test_probe_remains_studio_only_and_non_destructive(self):
        source = PROBE.read_text()
        self.assertIn('not RunService:IsStudio()', source)
        self.assertIn('CollectionService:GetTagged(TAG)', source)
        for action in ('model:Destroy()', 'model:PivotTo(', 'model:ScaleTo(',
                       'model.Parent = nil', 'LocalTransparencyModifier ='):
            self.assertNotIn(action, source)
        self.assertIn('Game1LodProbeClient', (ROOT/'default.project.json').read_text())


if __name__ == '__main__':
    unittest.main()
