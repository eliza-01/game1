"""M444: resource receipts / spends head-anchored, with measured content boxes."""
import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from options_store import (OptionsStore, UI_PROFILE_DEFAULTS,
                           normalize_ui_presentation)


def text(path):
    return (ROOT / path).read_text(encoding='utf-8')


class M444ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = OptionsStore(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_both_device_profiles_have_independent_padding_defaults(self):
        snapshot = self.store.snapshot()['uiPresentation']
        for device in ('desktop','mobile'):
            self.assertEqual(snapshot[device]['resource']['paddingPx'], 5)
            self.assertEqual(snapshot[device]['notification']['paddingPx'], 5)
        self.assertEqual(normalize_ui_presentation({}), UI_PROFILE_DEFAULTS)

    def test_padding_bounds_and_old_profile_upgrade_keep_old_settings(self):
        old = deepcopy(self.store.snapshot())
        old['uiPresentation']['desktop']['resource']['offsetXPx'] = -32
        old['uiPresentation']['desktop']['resource']['fontPx'] = 22
        old['uiPresentation']['desktop']['resource']['durationSeconds'] = 2.6
        old['uiPresentation']['mobile']['notification']['offsetYPx'] = -17
        for device in ('desktop','mobile'):
            for section in ('notification', 'resource'):
                del old['uiPresentation'][device][section]['paddingPx']
        (self.root / 'assets/manifests/options.json').write_text(json.dumps(old),encoding='utf-8')
        reopened = OptionsStore(self.root)
        actual = reopened.snapshot()['uiPresentation']
        self.assertEqual(actual['desktop']['resource']['offsetXPx'], -32)
        self.assertEqual(actual['desktop']['resource']['fontPx'], 22)
        self.assertEqual(actual['desktop']['resource']['durationSeconds'], 2.6)
        self.assertEqual(actual['mobile']['notification']['offsetYPx'], -17)
        for device in ('desktop','mobile'):
            for section in ('notification','resource'):
                self.assertEqual(actual[device][section]['paddingPx'], 5)
        generated = (self.root / 'src/shared/GameOptionsRegistry.luau').read_text(encoding='utf-8')
        self.assertIn('paddingPx = 5', generated)
        for device,section,value in [('desktop','notification',0), ('mobile','resource',24)]:
            answer = reopened.update({'uiPresentation': {device:{section:{'paddingPx':value}}}})
            self.assertEqual(answer['uiPresentation'][device][section]['paddingPx'], value)
        for value in (-1,25,3.5,True,float('nan')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                reopened.update({'uiPresentation':{'desktop':{'resource':{'paddingPx':value}}}})

    def test_preview_does_not_save_padding(self):
        payload = deepcopy(self.store.snapshot()['uiPresentation']['desktop'])
        payload['resource']['paddingPx'] = 13
        response = self.store.preview_ui({'device':'desktop','settings':payload})
        self.assertFalse(response['saved'])
        self.assertEqual(self.store.snapshot()['uiPresentation']['desktop']['resource']['paddingPx'],5)
        self.assertEqual(self.store.snapshot_with_debug()['uiPresentationDebugDraft']['settings']['resource']['paddingPx'],13)


class M444WiringTests(unittest.TestCase):
    def test_gain_and_spend_share_one_authoritative_event(self):
        server = text('src/server/world/HouseFireplaceService.luau')
        client = text('src/client/world/HouseSocketPromptController.luau')
        self.assertIn('icon = "meal", amount = 1, label = "Блюдо"',server)
        self.assertNotIn('notify(player, "Блюдо получено")',server)
        self.assertIn('kind = "resource"',server)
        self.assertIn('ResourceFeedback.Show(payload.items)',client)
        self.assertNotIn('showFloatingSpend(',client)
        self.assertIn('if payload.kind == "toast"',client)
        self.assertIn('if payload.kind == "resource"',client)

    def test_world_billboard_uses_head_bone_or_head_part_and_measured_text(self):
        code = text('src/client/world/FloatingResourceFeedback.luau')
        for key in ('SpatialRoot.IsCustom(player)', 'FindFirstChild("head", true)',
                    'head:IsA("Bone")', 'FindFirstChild("Head", true)',
                    'SpatialRoot.Get(player)', 'billboard.Adornee = anchor',
                    'billboard.StudsOffsetWorldSpace', 'WorldInputPassthrough',
                    'TextService:GetTextSize', 'config.paddingPx',
                    'width = measured.X + padding * 2', 'height = measured.Y + padding * 2',
                    'index - 1', 'config.offsetXPx', 'config.offsetYPx',
                    'TweenService:Create(box', 'task.delay(duration + 0.1',
                    'function Feedback.Preview'):
            self.assertIn(key,code)
        self.assertNotIn('SpendHost',code)
        self.assertNotIn('Instance.new("Part")',code)

    def test_notification_content_box_and_both_editors_share_schema(self):
        controller = text('src/client/world/HouseSocketPromptController.luau')
        for key in ('TextService:GetTextSize', 'config.paddingPx',
                    'notification.Size = UDim2.fromOffset(bounds.X + 2 * padding, bounds.Y + 2 * padding)',
                    'notification.Visible = true'):
            self.assertIn(key,controller)
        contract = text('src/shared/world/UiPresentationContract.luau')
        self.assertIn('paddingPx=5',contract)
        self.assertIn('paddingPx={0,24}',contract)
        options_js = text('system/control-center/static/options.js')
        debug = text('src/client/dev/UiPresentationDebugController.luau')
        for code in (options_js,debug):
            self.assertIn('paddingPx',code)
        self.assertIn('ResourceFeedback.Preview(cfg)',debug)
        self.assertIn('if resourcePreview then resourcePreview:Destroy()',debug)


if __name__ == '__main__':
    unittest.main()
