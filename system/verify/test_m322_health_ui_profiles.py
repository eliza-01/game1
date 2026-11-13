"""M322 health UI independently authored desktop/mobile options and Studio previews."""
from pathlib import Path
import json
import re
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from options_store import (OptionsStore, HEALTH_UI_DEFAULTS, normalize_health_profile,
                           normalize_health_ui)


def source(path):
    return (ROOT / path).read_text(encoding='utf-8')


class OptionsHealthContract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = OptionsStore(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_upgrade_of_previous_m321_options_keeps_camera_and_combat(self):
        legacy = self.store.snapshot()
        old_camera = legacy['camera'].copy()
        old_combat = legacy['combat'].copy()
        old_camera['distance'] = 12.5
        legacy['camera'] = old_camera
        legacy.pop('healthUi', None)
        legacy.pop('debugUi', None)
        path = self.root / 'assets/manifests/options.json'
        path.write_text(json.dumps(legacy), encoding='utf-8')
        OptionsStore(self.root)
        upgraded = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(upgraded['camera'], old_camera)
        self.assertEqual(upgraded['combat'], old_combat)
        self.assertEqual(upgraded['healthUi'], HEALTH_UI_DEFAULTS)
        self.assertFalse(upgraded['debugUi']['mobile']['showPublishedControls'])
        OptionsStore(self.root)  # idempotent
        self.assertEqual(json.loads(path.read_text(encoding='utf-8')), upgraded)

    def test_first_boot_generates_two_profiles_and_hidden_published_controls(self):
        settings = self.store.snapshot()
        self.assertEqual(set(settings['healthUi']), {'desktop', 'mobile'})
        self.assertEqual(settings['healthUi']['desktop']['screen']['width'], 320)
        self.assertEqual(settings['healthUi']['mobile']['screen']['width'], 214)
        self.assertFalse(settings['debugUi']['desktop']['showPublishedControls'])
        self.assertFalse(settings['debugUi']['mobile']['showPublishedControls'])
        registry = (self.root / 'src/shared/GameOptionsRegistry.luau').read_text()
        self.assertIn('healthUi = table.freeze', registry)
        self.assertIn('showPublishedControls = ', registry)

    def test_mutation_of_desktop_does_not_touch_mobile_and_changes_generated_runtime(self):
        old_mobile = self.store.snapshot()['healthUi']['mobile']
        saved = self.store.update({'healthUi': {'desktop': {'screen': {'width': 260, 'height': 14},
                                                         'colors': {'green': '#22BBAA'},
                                                         'self': {'enabled': False}}}})
        self.assertEqual(saved['healthUi']['mobile'], old_mobile)
        self.assertEqual(saved['healthUi']['desktop']['screen']['width'], 260)
        self.assertFalse(saved['healthUi']['desktop']['self']['enabled'])
        registry = (self.root / 'src/shared/GameOptionsRegistry.luau').read_text()
        self.assertIn('width = 260', registry)
        self.assertIn('green = "#22BBAA"', registry)
        saved = self.store.update({'healthUi': {'mobile': {'monster': {'offsetStuds': 5.5}}}})
        self.assertEqual(saved['healthUi']['desktop']['screen']['width'], 260)
        self.assertEqual(saved['healthUi']['mobile']['monster']['offsetStuds'], 5.5)

    def test_strict_invalid_untrusted_profile(self):
        invalid = [
            {'screen': {'width': -5}}, {'screen': {'border': 300}},
            {'screen': {'height': float('nan')}}, {'screen': {'enabled': 1}},
            {'colors': {'red': 'red'}}, {'foo': {'width': 99}},
            {'screen': {'script': 42}},
        ]
        for case in invalid:
            with self.subTest(case=case), self.assertRaises(ValueError):
                self.store.update({'healthUi': {'desktop': case}})
        self.assertEqual(self.store.snapshot()['healthUi']['desktop'], HEALTH_UI_DEFAULTS['desktop'])

    def test_studio_draft_is_not_persisted_until_explicit_save(self):
        data = self.store.snapshot()
        draft = {'device': 'mobile', 'settings': data['healthUi']['mobile']}
        draft['settings']['monster']['width'] = 188
        result = self.store.preview_health_ui(draft)
        self.assertFalse(result['saved'])
        self.assertEqual(self.store.snapshot()['healthUi']['mobile']['monster']['width'], 150)
        current = self.store.snapshot_with_debug()
        self.assertEqual(current['healthUiDebugDraft']['settings']['monster']['width'], 188)
        self.assertGreater(current['healthUiDebugDraftAt'], 0)
        self.store.update({'healthUi': {'mobile': current['healthUiDebugDraft']['settings']}})
        self.assertEqual(self.store.snapshot()['healthUi']['mobile']['monster']['width'], 188)
        with self.assertRaises(ValueError):
            self.store.preview_health_ui({'device': 'console', 'settings': {}})

    def test_toggle_published_controls_does_not_affect_combat_or_camera(self):
        old = self.store.snapshot()
        new = self.store.update({'debugUi': {'desktop': {'showPublishedControls': True}}})
        self.assertTrue(new['debugUi']['desktop']['showPublishedControls'])
        self.assertFalse(new['debugUi']['mobile']['showPublishedControls'])
        self.assertEqual(old['combat'], new['combat'])
        self.assertEqual(old['camera'], new['camera'])
        self.assertIn('showPublishedControls = true',
                      (self.root / 'src/shared/GameOptionsRegistry.luau').read_text())
        with self.assertRaises(ValueError):
            self.store.update({'debugUi': {'desktop': {'showPublishedControls': 'false'}}})


class HealthRuntimeIntegration(unittest.TestCase):
    def test_runtime_style_shared_by_player_and_monster_and_published_gate(self):
        settings = source('src/client/combat/HealthUiSettings.luau')
        view = source('src/client/combat/HealthBarView.luau')
        hud = source('src/client/combat/PlayerHealthHudController.luau')
        over = source('src/client/combat/OverheadHealthController.luau')
        picker = source('src/client/weapon/WeaponSelectionController.luau')
        self.assertIn('TouchEnabled and not UserInputService.KeyboardEnabled', settings)
        self.assertIn('Settings.Changed', settings)
        self.assertIn('Settings.Current().screen', hud)
        self.assertIn('view.ApplyStyle(style)', over)
        self.assertIn('gui.StudsOffsetWorldSpace = Vector3.new(0, baseOffset + spec.offsetStuds, 0)', view)
        self.assertIn('first:upper() .. tail:lower()', view)
        for file in (view,hud):
            self.assertIn('ratio <= 0.30', file)
            self.assertIn('ratio <= 0.65', file)
            self.assertIn('TweenService:Create(fill', file)
            self.assertNotIn('SetAttribute("HP"', file)
        self.assertIn('PublishedDebugAccess.ClientAllowed()', picker)

    def test_studio_draft_transport_uses_existing_authenticated_bridge(self):
        client = source('src/client/dev/HealthUiDebugController.luau')
        server = source('src/server/dev/HealthUiDebugService.luau')
        bridge = source('system/studio-plugin/modules/StudioOptionsDraftBridge.luau')
        self.assertIn('PublishedDebugAccess.ClientAllowed()', client)
        self.assertIn('PublishedDebugAccess.ServerEnabled()', server)
        self.assertIn('PublishedDebugAccess.ServerAllowed(player)', server)
        self.assertIn('Settings.Preview(device, drafts[device])', client)
        self.assertIn('remote:FireServer({device=chosen, settings=snapshot})', client)
        self.assertIn('cooldown[player]', server)
        self.assertIn('"Payload"', server)
        self.assertIn('specs', bridge)
        self.assertIn('/api/options/camera-draft', bridge)
        self.assertIn('/api/options/health-ui-draft', bridge)
        self.assertIn('X-Control-Token', bridge)
        self.assertFalse((ROOT/'system/studio-plugin/modules/StudioCameraDraftBridge.luau').exists())
        self.assertIn('OptionsStore', source('system/control-center/host_agent.py'))
        self.assertIn('health-ui-draft', source('system/control-center/api/write_world.py'))

    def test_web_profile_controls_and_drafts(self):
        index = source('system/control-center/static/index.html')
        script = source('system/control-center/static/options.js')
        for token in ['health-ui-desktop','health-ui-mobile','health-ui-fields',
                      'option-published-debug-buttons', 'health-ui-import', 'health-ui-save']:
            self.assertIn(token, index)
        self.assertIn('game1HealthCapture()', script)
        self.assertIn('game1HealthValidate()', script)
        self.assertIn('game1HealthDraftStatus', script)
        self.assertIn('{healthUi:{[device]:settings}}', script)
        self.assertIn('showPublishedControls', script)

if __name__ == '__main__':
    unittest.main()
