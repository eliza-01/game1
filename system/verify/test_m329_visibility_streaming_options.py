"""M329: per-device monster-label distance; single-place engine streaming target."""
from pathlib import Path
import copy
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from options_store import OptionsStore, HEALTH_UI_DEFAULTS


def source(path):
    return (ROOT / path).read_text(encoding='utf-8')


class DistanceOptions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = OptionsStore(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_fresh_profile_and_shared_world_target(self):
        options = self.store.snapshot()
        self.assertEqual(options['healthUi']['desktop']['monster']['maxDistanceStuds'], 100)
        self.assertEqual(options['healthUi']['mobile']['monster']['maxDistanceStuds'], 100)
        self.assertEqual(options['worldStreaming']['targetRadiusStuds'], 150)
        self.assertIn('maxDistanceStuds = 100',
                      (self.root / 'src/shared/GameOptionsRegistry.luau').read_text())

    def test_old_profile_migrates_without_losing_existing_customization(self):
        data = self.store.snapshot()
        data['healthUi']['desktop']['monster']['width'] = 211
        for device in ('desktop', 'mobile'):
            del data['healthUi'][device]['monster']['maxDistanceStuds']
        del data['worldStreaming']
        manifest = self.root / 'assets/manifests/options.json'
        manifest.write_text(json.dumps(data), encoding='utf-8')
        OptionsStore(self.root)
        migrated = json.loads(manifest.read_text(encoding='utf-8'))
        self.assertEqual(migrated['healthUi']['desktop']['monster']['width'], 211)
        self.assertEqual(migrated['healthUi']['desktop']['monster']['maxDistanceStuds'], 100)
        self.assertEqual(migrated['worldStreaming']['targetRadiusStuds'], 150)

    def test_pc_mobile_independent_label_distance(self):
        result = self.store.update({'healthUi': {'desktop': {'monster': {'maxDistanceStuds': 150}}}})
        self.assertEqual(result['healthUi']['desktop']['monster']['maxDistanceStuds'], 150)
        self.assertEqual(result['healthUi']['mobile']['monster']['maxDistanceStuds'], 100)
        result = self.store.update({'healthUi': {'mobile': {'monster': {'maxDistanceStuds': 80}}}})
        self.assertEqual(result['healthUi']['desktop']['monster']['maxDistanceStuds'], 150)
        self.assertEqual(result['healthUi']['mobile']['monster']['maxDistanceStuds'], 80)

    def test_world_target_is_global_and_validated(self):
        self.assertEqual(self.store.update({'worldStreaming': {'targetRadiusStuds': 256}})
                         ['worldStreaming']['targetRadiusStuds'], 256)
        for bad in (0, 64, 95, 4097, 150.2, '150', True):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.store.update({'worldStreaming': {'targetRadiusStuds': bad}})
        self.assertEqual(self.store.snapshot()['worldStreaming']['targetRadiusStuds'], 256)

    def test_monster_radius_validation(self):
        for bad in (19, 801, float('nan'), '100', False):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.store.update({'healthUi': {'desktop': {'monster': {'maxDistanceStuds': bad}}}})


class RuntimeDistanceContracts(unittest.TestCase):
    def test_player_center_distance_gate_precedes_focus_and_aggro(self):
        controller = source('src/client/combat/OverheadHealthController.luau')
        self.assertIn('local playerRoot = if character then anchorFor(character)', controller)
        self.assertIn('style.monster.maxDistanceStuds', controller)
        self.assertIn('delta:Dot(delta) <= radiusSquared', controller)
        self.assertIn('view.SetVisible(alive and inRange', controller)
        self.assertIn('or focused or attackingUs', controller)
        self.assertIn('ELAPSED_STEP = 0.10', controller)
        self.assertIn('gui.MaxDistance = math.max(260', source('src/client/combat/HealthBarView.luau'))

    def test_asset_manager_editors_and_studio_debug_share_the_field(self):
        self.assertIn("'maxDistanceStuds'", source('system/control-center/static/options.js'))
        studio = source('src/client/dev/HealthUiDebugController.luau')
        self.assertIn('maxDistanceStuds={20,800,10}', studio)
        self.assertIn('"maxDistanceStuds"', studio)

    def test_workspace_target_not_falsely_written_in_game(self):
        options_ui = source('system/control-center/static/index.html')
        js = source('system/control-center/static/options.js')
        self.assertIn('option-world-streaming-radius', options_ui)
        self.assertIn('Studio Command Bar', options_ui)
        self.assertIn('set("StreamingTargetRadius", ${radius})', js)
        self.assertNotIn('Workspace.StreamingTargetRadius =', source('src/client/combat/OverheadHealthController.luau'))


if __name__ == '__main__':
    unittest.main()
