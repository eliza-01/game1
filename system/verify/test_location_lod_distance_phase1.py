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

    def test_debug_probe_and_studio_hud_are_retired(self):
        self.assertFalse((ROOT/'src/client/world/LocationLodStudioProbe.luau').exists())
        self.assertFalse((ROOT/'src/lod-probe').exists())
        project = (ROOT/'default.project.json').read_text()
        self.assertNotIn('Game1LodProbeClient', project)
        streamer = (ROOT/'src/client/world/LocationWorldStreamer.luau').read_text()
        self.assertNotIn('Game1RuntimeLodStatus', streamer)
        self.assertNotIn('preview:Stats()', streamer)
        self.assertIn('preview:Resolve(cameraPosition)', streamer)

if __name__ == '__main__': unittest.main()
