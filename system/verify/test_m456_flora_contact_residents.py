"""M456: persisted Flora policy, resident asset publication and client VFX boundaries."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from copy import deepcopy

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from options_store import OptionsStore
from services.flora_effect_settings import DEFAULTS, normalize_flora, validate_residents


class FloraSettingsM456(unittest.TestCase):
    def test_default_has_bounded_eight_leaves_and_published_asset(self):
        cfg = normalize_flora({})
        self.assertEqual(cfg['leavesPerBurst'], 8)
        self.assertEqual(cfg['cooldownSeconds'], 1.5)
        self.assertEqual(cfg['residentAssets'], ['leaf_01'])
        self.assertEqual(cfg['leafAssetSlug'], 'leaf_01')
        validate_residents(ROOT, cfg)

    def test_validation_rejects_unsafe_or_unbounded_inputs(self):
        invalid = [
            {'leavesPerBurst': 21}, {'leavesPerBurst': 3.25},
            {'maxActiveLeaves': 2}, {'maxActiveLeaves': 8, 'leavesPerBurst': 12},
            {'spreadRadiusStuds': -5}, {'spreadRadiusStuds': float('nan')},
            {'cooldownSeconds': 0}, {'durationSeconds': 10},
            {'residentAssets': []}, {'residentAssets': ['leaf_01', 'leaf_01']},
            {'residentAssets': ['__bad']}, {'residentAssets': ['something'], 'leafAssetSlug': 'leaf_01'},
            {'leafAssetSlug': 'bush_02', 'residentAssets': ['bush_02']},
            {'enabled': 1}, {'unknown': 3},
        ]
        for data in invalid:
            with self.subTest(data=data), self.assertRaises(ValueError):
                cfg = normalize_flora(data)
                validate_residents(ROOT, cfg)

    def test_can_pin_second_published_single_mesh_asset(self):
        cfg = normalize_flora({'residentAssets': ['leaf_01', 'bush_02']})
        validate_residents(ROOT, cfg)
        with self.assertRaises(ValueError):
            validate_residents(ROOT, normalize_flora({'residentAssets': ['leaf_01', 'thuja_02']}))

    def test_update_merges_without_erasing_unrelated_options(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dst = root / 'assets/manifests'
            dst.mkdir(parents=True)
            (dst / 'options.json').write_bytes((ROOT / 'assets/manifests/options.json').read_bytes())
            (dst / 'location-assets.json').write_bytes((ROOT / 'assets/manifests/location-assets.json').read_bytes())
            store = OptionsStore(root)
            before = store.snapshot()
            changed = store.update({'flora': {'leavesPerBurst': 13, 'cooldownSeconds': 2.25,
                'residentAssets': ['leaf_01', 'bush_02']}})
            self.assertEqual(changed['flora']['leavesPerBurst'], 13)
            self.assertEqual(changed['flora']['cooldownSeconds'], 2.25)
            self.assertEqual(changed['flora']['residentAssets'], ['leaf_01', 'bush_02'])
            self.assertEqual(changed['rotations'], before['rotations'])
            self.assertEqual(changed['socketRanges'], before['socketRanges'])
            self.assertIn('residentAssets = table.freeze({"leaf_01", "bush_02"})',
                (root / 'src/shared/GameOptionsRegistry.luau').read_text())
            # persisted settings survive fresh reader and re-generation
            self.assertEqual(OptionsStore(root).snapshot()['flora'], changed['flora'])
            with self.assertRaises(ValueError):
                store.update({'flora': {'residentAssets': ['leaf_01', 'thuja_02']}})
            self.assertEqual(store.snapshot()['flora'], changed['flora'])

    def test_runtime_boundaries_and_initialization(self):
        server = (ROOT / 'src/server/world/LocationLodTemplateService.luau').read_text()
        residents = (ROOT / 'src/server/world/LocationResidentTemplateService.luau').read_text()
        index = (ROOT / 'src/client/world/FloraContactIndex.luau').read_text()
        pool = (ROOT / 'src/client/world/FloraLeafPool.luau').read_text()
        runtime = (ROOT / 'src/client/world/FloraLeafBurstController.luau').read_text()
        init = (ROOT / 'src/client/init.client.luau').read_text()
        self.assertIn('LocationResidentTemplateService', server)
        self.assertIn('Service.Start(loadPrototype', residents)
        self.assertIn('Game1ResidentEffectTemplates', residents)
        self.assertIn('ContentProvider:PreloadAsync', pool)
        self.assertIn('allReady', pool)
        self.assertIn('Pool.Release(', runtime)
        self.assertIn('Index.Find(', runtime)
        self.assertIn('lastContact', runtime)
        self.assertIn('Game1DecoAssetSlug', index)
        self.assertIn('LandscapeAssetSlug', index)
        self.assertIn('Contract.ReadManifest(marker)', index)
        self.assertIn('Contract.Validate(manifest, Registry)', index)
        self.assertIn('placement.components', index)
        self.assertIn('compiledTargets[slug] = true', index)
        self.assertIn('Workspace.DescendantAdded', index)
        self.assertNotIn(':Touched:Connect', index + runtime)
        self.assertNotIn('FireServer(', index + runtime + pool)
        self.assertNotIn('Instance.new("MeshPart")', index + runtime + pool)
        self.assertIn('FloraLeafBurstController', init)
        self.assertNotIn('FloraLeafBurstController',
            (ROOT / 'src/client/world/LocationWorldStreamer.luau').read_text())
        html = (ROOT / 'system/control-center/static/index.html').read_text()
        for key in DEFAULTS:
            self.assertIn('option-flora-' + key, html)


if __name__ == '__main__':
    unittest.main()
