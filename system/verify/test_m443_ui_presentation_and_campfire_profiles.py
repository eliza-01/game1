"""M443: UI profiles, Studio preview transport, and campfire pot visuals."""
from pathlib import Path
from copy import deepcopy
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from options_store import OptionsStore, UI_PROFILE_DEFAULTS, normalize_ui_profile


def source(filename):
    return (ROOT / filename).read_text(encoding='utf-8')


class UiPresentationOptionsM443(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = OptionsStore(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_first_boot_keeps_independent_devices_and_generates_luau(self):
        options = self.store.snapshot()
        self.assertEqual(options['uiPresentation'], UI_PROFILE_DEFAULTS)
        registry = (self.root / 'src/shared/GameOptionsRegistry.luau').read_text(encoding='utf-8')
        self.assertIn('uiPresentation = table.freeze', registry)
        self.assertIn('durationSeconds = 2.7', registry)
        self.assertIn('widthPx = 272', registry)

    def test_upgrade_old_manifest_keeps_unrelated_settings(self):
        before = self.store.snapshot()
        before['camera']['distance'] = 12.5
        before['healthUi']['desktop']['screen']['width'] = 290
        before.pop('uiPresentation')
        manifest = self.root / 'assets/manifests/options.json'
        manifest.write_text(json.dumps(before), encoding='utf-8')
        reopened = OptionsStore(self.root)
        after = reopened.snapshot()
        self.assertEqual(after['camera'], before['camera'])
        self.assertEqual(after['healthUi'], before['healthUi'])
        self.assertEqual(after['uiPresentation'], UI_PROFILE_DEFAULTS)
        OptionsStore(self.root)
        self.assertEqual(json.loads(manifest.read_text(encoding='utf-8')), after)

    def test_save_one_device_only_and_partial_fields(self):
        original = self.store.snapshot()
        new = self.store.update({'uiPresentation': {'desktop': {
            'interaction': {'offsetXPx': -42, 'fontPx': 20},
            'notification': {'durationSeconds': 4.5},
            'resource': {'risePx': 100},
        }}})
        self.assertEqual(new['uiPresentation']['mobile'], original['uiPresentation']['mobile'])
        self.assertEqual(new['uiPresentation']['desktop']['status'], original['uiPresentation']['desktop']['status'])
        self.assertEqual(new['uiPresentation']['desktop']['interaction']['offsetXPx'], -42)
        self.assertEqual(new['uiPresentation']['desktop']['notification']['durationSeconds'], 4.5)
        new = self.store.update({'uiPresentation': {'mobile': {'status': {'timerFontPx': 24}}}})
        self.assertEqual(new['uiPresentation']['desktop']['interaction']['offsetXPx'], -42)
        self.assertEqual(new['uiPresentation']['mobile']['status']['timerFontPx'], 24)

    def test_strict_bounds_type_unknown_and_decimal_pixel_rejection(self):
        cases = (
            {'desktop': {'interaction': {'offsetXPx': 501}}},
            {'mobile': {'notification': {'durationSeconds': 16}}},
            {'desktop': {'interaction': {'widthPx': 25}}},
            {'desktop': {'interaction': {'offsetYPx': 0.5}}},
            {'desktop': {'interaction': {'fontPx': True}}},
            {'desktop': {'interaction': {'fontPx': float('nan')}}},
            {'desktop': {'interaction': {'fontPx': float('inf')}}},
            {'desktop': {'other': {'fontPx': 22}}},
            {'desktop': {'interaction': {'sneaky': 22}}},
            {'console': {}},
        )
        for change in cases:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.store.update({'uiPresentation': change})
        self.assertEqual(self.store.snapshot()['uiPresentation'], UI_PROFILE_DEFAULTS)

    def test_draft_only_does_not_write_and_rejects_extra_fields(self):
        draft = deepcopy(UI_PROFILE_DEFAULTS['mobile'])
        draft['resource']['durationSeconds'] = 3.2
        answer = self.store.preview_ui({'device': 'mobile', 'settings': draft})
        self.assertFalse(answer['saved'])
        self.assertEqual(self.store.snapshot()['uiPresentation'], UI_PROFILE_DEFAULTS)
        snapshot = self.store.snapshot_with_debug()
        self.assertEqual(snapshot['uiPresentationDebugDraft']['settings'], draft)
        self.assertGreater(snapshot['uiPresentationDebugDraftAt'], 0)
        with self.assertRaises(ValueError):
            self.store.preview_ui({'device':'mobile','settings':draft, 'script': 'bad'})
        with self.assertRaises(ValueError):
            self.store.preview_ui({'device':'console','settings':draft})

    def test_luau_fallback_matches_python_defaults_and_field_bounds(self):
        contract = source('src/shared/world/UiPresentationContract.luau')
        options = source('src/shared/GameOptions.luau')
        for group in UI_PROFILE_DEFAULTS['desktop']:
            self.assertIn(group + ' = table.freeze', contract)
        for profile in UI_PROFILE_DEFAULTS.values():
            for fields in profile.values():
                for key, val in fields.items():
                    self.assertIn(key + '=', contract)
        self.assertIn('Contract.Validate', contract)
        self.assertIn('UiPresentationContract', options)
        self.assertIn('profiles[device] or fallback[device]', options)


class UiPresentationIntegrationM443(unittest.TestCase):
    def test_studio_plugin_draft_roundtrip_is_authenticated(self):
        bridge = source('system/studio-plugin/modules/StudioOptionsDraftBridge.luau')
        server = source('src/server/dev/UiPresentationDebugService.luau')
        client = source('src/client/dev/UiPresentationDebugController.luau')
        write = source('system/control-center/api/write_world.py')
        for token in ('Game1UiPresentationDebug','/api/options/ui-presentation-draft','X-Control-Token'):
            self.assertIn(token, bridge)
        for token in ('Access.ServerEnabled()', 'Access.ServerAllowed(player)',
                      'Contract.Validate(input.device, input.settings)', 'lastSent[player]', 'Payload'):
            self.assertIn(token, server)
        for token in ('Access.ClientAllowed()', 'Settings.Preview(device,drafts[device])',
                      'remote:FireServer({device=selectedDevice,settings=snapshot})',
                      'Settings.Preview(nil,nil)', 'showSample()', 'UiPresentationDebugChanged'):
            self.assertIn(token, client)
        self.assertIn('options_store.preview_ui(body())', write)
        self.assertIn('UiPresentationDebugService', source('src/server/bootstrap/ServiceCatalog.luau'))
        self.assertIn('UiPresentationDebugController', source('src/client/init.client.luau'))

    def test_all_four_runtime_surfaces_read_same_settings(self):
        prompt = source('src/client/world/HouseSocketPromptController.luau')
        fireplace = source('src/client/world/HouseFireplaceController.luau')
        for group in ('interaction', 'notification', 'resource'):
            self.assertIn(f'UiSettings.Current().{group}', prompt)
        self.assertIn('UiSettings.Current().status', fireplace)
        self.assertIn('UiSettings.Changed:Connect', fireplace)
        self.assertIn('UiSettings.Changed:Connect', prompt)
        self.assertIn('UiInputGuard', source('src/client/character/CameraController.luau'))
        self.assertIn('WorldInputPassthrough', prompt)

    def test_web_has_comprehensive_profile_controls(self):
        html = source('system/control-center/static/index.html')
        js = source('system/control-center/static/options.js')
        for token in ('option-ui-desktop','option-ui-mobile','option-ui-fields',
                      'option-ui-import','option-ui-save'):
            self.assertIn(token, html)
        for token in ('interaction','status','notification','resource','durationSeconds',
                      'game1UiCapture','game1UiRead','game1UiDraftStatus',
                      '{uiPresentation:{[device]:game1UiRead()}}'):
            self.assertIn(token, js)

    def test_campfire_both_fire_and_light_switch_with_pot_no_timer_restart(self):
        engine = source('src/server/world/HouseFireplaceService.luau')
        config = source('src/shared/world/FireplaceMechanicsConfig.luau')
        for token in ('CampfireFire','CampfireLight','Size = 4.0','Heat = 8.0',
                      'Brightness = 2.0','Range = 18.0'):
            self.assertIn(token,config)
        self.assertIn('local referenceMode = state.kind == "campfire" and state.potInstance == nil',engine)
        self.assertIn('if referenceMode then Config.CampfireFire else Config.Fire',engine)
        self.assertIn('if referenceMode then Config.CampfireLight else Config.Light',engine)
        self.assertIn('light.Enabled = enabled and lightPreset.Enabled',engine)
        # Both transitions update the visuals while conserving fuelEndsAt/fuelRevision.
        start=engine.index('local function removePot')
        end=engine.index('local function finishCooking')
        transitions=engine[start:end]
        self.assertEqual(transitions.count('ensureFireVisual(state, state.fuelStage == "fire")'), 2)
        self.assertNotIn('fuelRevision +=',transitions)
        self.assertNotIn('fuelEndsAt =',transitions)


if __name__ == '__main__':
    unittest.main()
