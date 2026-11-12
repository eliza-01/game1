"""M292 regression contracts for Edit-mode Landscape Painter placement recovery.

These are source/packaging checks; Studio cursor and published-model rendering
still require a real Edit-mode smoke test after installing the plugin.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'system' / 'landscape-plugin'


def source(path):
    return (BASE / path).read_text(encoding='utf-8')


class LandscapePainterPlacementRecovery(unittest.TestCase):
    def test_session_owns_mouse_before_initial_preview_and_fails_cleanly(self):
        main = source('LandscapePainter.server.luau')
        start = main.split('local function start(kind)', 1)[1].split('local function safe(action)', 1)[0]
        self.assertLess(start.index('plugin:Activate(true)'), start.index('active = kind'))
        self.assertLess(start.index('active = kind'), start.index('assets:Start()'))
        self.assertIn('plugin:IsActivatedWithExclusiveMouse()', start)
        self.assertIn('local ok, started = pcall(function()', start)
        self.assertIn('if not ok or not started then', start)
        self.assertIn('stop()', start)

    def test_input_errors_are_visible_and_cancel_studio_takeover(self):
        main = source('LandscapePainter.server.luau')
        self.assertIn('local ok, reason = pcall(callback)', main)
        self.assertIn('handleViewportInput("cursor", function() assets:UpdateCursor(false) end)', main)
        self.assertIn('handleViewportInput("click", function() assets:Click() end)', main)
        self.assertIn('Studio: другой инструмент забрал мышь', main)
        self.assertIn('assetUI:SetStatus(message)', main)
        widget = source('modules/LandscapeAssetsWidget.luau')
        self.assertLess(widget.index('self.modeStatus = label'), widget.index('self.target = button'))
        self.assertIn('function AssetsWidget:SetStatus(message)', widget)
        self.assertIn('self.modeStatus.Text = tostring(message)', widget)

    def test_preview_exception_cannot_abort_valid_hit_or_click(self):
        placement = source('modules/LandscapeAssetPlacement.luau')
        cursor = placement.split('function Placement:UpdateCursor(force)', 1)[1].split('local function writeMetadata', 1)[0]
        self.assertLess(cursor.index('self.cursor = {'), cursor.index('local ghostOK, ghostError = pcall'))
        self.assertIn('local markerOK, markerError = pcall', cursor)
        self.assertIn('Ошибка отображения прицела:', cursor)
        self.assertIn('Прицел не видит поверхность', cursor)
        click = placement.split('function Placement:Click()', 1)[1].split('local function selectedModel(', 1)[0]
        self.assertIn('self:UpdateCursor(true)', click)
        self.assertIn('instance.Parent = folder', click)
        self.assertIn('FinishRecording(record, Enum.FinishRecordingOperation.Commit)', click)
        self.assertIn('if not clone then error(', placement)

    def test_detached_catalog_clone_policy_no_shared_loader_fork(self):
        catalog = source('modules/LandscapeAssetCatalog.luau')
        self.assertIn('self.loader:loadPublished(row)', catalog)
        self.assertIn('model.Archivable = true', catalog)
        self.assertIn('descendant.Archivable = true', catalog)
        self.assertIn('if model.Parent ~= nil then', catalog)
        self.assertNotIn('Instance.new("Model")', catalog)


if __name__ == '__main__':
    unittest.main()
