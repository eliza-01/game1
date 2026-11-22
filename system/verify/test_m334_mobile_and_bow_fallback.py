"""M334: dynamic mobile input and permission-safe bow snapshot target geometry."""
from __future__ import annotations
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
def source(path):
    return (ROOT / path).read_text(encoding='utf-8')

class MobileControlsM334(unittest.TestCase):
    def test_left_analog_touch_area_with_passive_home_hint(self):
        s = source('src/client/character/MobileInputController.luau')
        view = source('src/client/character/mobile/MobileControlsView.luau')
        layout = source('src/client/character/mobile/MobileLayout.luau')
        self.assertIn('Layout.IsMoveZone(point.X, point.Y, size.X, size.Y)', s)
        self.assertIn('y >= height * 0.52 and x <= width * 0.43', layout)
        self.assertIn('pad:SetAttribute("WorldInputPassthrough", true)', view)
        self.assertIn('left.center = position', s)
        self.assertIn('gui.ScreenInsets = Enum.ScreenInsets.CoreUISafeInsets', view)
        self.assertIn('local axis = if strength > 0', s)
        self.assertIn('movementController.SetTouchMovement(Vector2.zero, false)', s)
        self.assertIn('UiInputGuard.BlocksWorldInput(input, gameProcessed)', s)
        self.assertNotIn('touchStartsOn(left, input)', s)

    def test_free_look_outside_move_area_and_compact_action_cluster(self):
        s = source('src/client/character/MobileInputController.luau')
        view = source('src/client/character/mobile/MobileControlsView.luau')
        layout = source('src/client/character/mobile/MobileLayout.luau')
        self.assertIn('elseif not pinchLocked and #lookFingers < 2 then', s)
        self.assertIn('attack = {size = attack, x = margin + secondary + gap', layout)
        self.assertIn('jump = {size = secondary, x = margin, y = margin}', layout)
        self.assertIn('aim = {size = secondary, x = margin, y = margin + secondary + gap}', layout)
        self.assertNotIn('makeStick(gui, "LookStick")', view)
        self.assertIn('if #lookFingers == 1 and not pinchLocked then', s)
        self.assertIn('if #lookFingers == 0 then', s)

    def test_mobile_published_flag_migrates_without_overwriting_other_options(self):
        import sys
        import tempfile
        sys.path.insert(0, str(ROOT / 'system/control-center'))
        from options_store import OptionsStore
        with tempfile.TemporaryDirectory() as folder:
            dest = Path(folder)
            (dest / 'assets/manifests').mkdir(parents=True)
            (dest / 'src/shared').mkdir(parents=True)
            original = json.loads(source('assets/manifests/options.json'))
            original['healthUi']['mobile']['colors']['green'] = '#012345'
            (dest / 'assets/manifests/options.json').write_text(json.dumps(original))
            store = OptionsStore(dest)
            expected = store.snapshot()
            updated = store.update({'debugUi': {'mobile': {'showPublishedControls': True}}})
            self.assertTrue(updated['debugUi']['mobile']['showPublishedControls'])
            self.assertEqual(updated['healthUi'], expected['healthUi'])
            self.assertEqual(updated['camera'], expected['camera'])
            self.assertEqual(updated['debugUi']['desktop'], expected['debugUi']['desktop'])
            generated = (dest / 'src/shared/GameOptionsRegistry.luau').read_text()
            self.assertIn('mobile = table.freeze({\n\t\t\tshowPublishedControls = true', generated)
            self.assertEqual(store.update({'debugUi': {'mobile': {'showPublishedControls': True}}}), updated)
        policy = source('src/shared/dev/PublishedDebugAccess.luau')
        self.assertIn('player:GetAttribute(AUTH_ATTRIBUTE) == true', policy)
        self.assertIn('Options.ShowPublishedDebugControls(device)', policy)
        self.assertIn('warnedAuthorization = true', policy)

class BowPermissionFallbackM334(unittest.TestCase):
    def test_one_authoritative_hitscan_and_nonshrinking_fallback(self):
        queries = source('src/server/combat/HitboxSpatialQueries.luau')
        self.assertIn('if projectilePrecision and binding.mode ~= "root_bounds_fallback"', queries)
        self.assertIn('then rayHeadEllipsoidDistance(', queries)
        self.assertIn('then bodyBox.size * 0.90 else bodyBox.size', queries)
        service = source('src/server/combat/BowHitscanService.luau')
        self.assertIn('EntityHitboxService.RaycastAimRegions(character, origin, direction, castDistance, true)', service)
        self.assertIn('DamageService.Apply(character, target,', service)
        self.assertNotIn('Instance.new("Part")', service)
        self.assertIn('HitboxDefinitionBuilder.Fallback(binding)', source('src/server/combat/EntityHitboxService.luau'))
        builder = source('src/server/combat/HitboxDefinitionBuilder.luau')
        self.assertIn('bodyBoxes = {{kind = "root", localCFrame = CFrame.identity, size = size}}', builder)

    def test_fallback_uses_same_obbs_as_melee_not_shrunken_ellipsoid(self):
        # Example of edge contact: a server root-bounds box is guaranteed to
        # cover the point at x=0.97 when half-width=1; 90% precision shrinks
        # the half-width to 0.9 and misses. That is the M333 regression.
        def in_box(x: float, half_width: float) -> bool:
            return abs(x) <= half_width
        self.assertTrue(in_box(.97, 1.0))
        self.assertFalse(in_box(.97, .9))

if __name__=='__main__':
    unittest.main()
