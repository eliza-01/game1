"""M282 plugin integration invariants; Studio execution requires manual smoke test."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / 'system' / 'landscape-plugin'


def source(name: str) -> str:
    return (PLUGIN / name).read_text(encoding='utf-8')


class LandscapePluginM282Tests(unittest.TestCase):
    def test_separate_rojo_artifact_with_all_declared_modules(self):
        project = json.loads(source('plugin.project.json'))
        self.assertEqual(project['name'], 'Game1LandscapePainter')
        mapped = {key: value['$path'] for key, value in project['tree']['modules'].items()
                  if key != '$className'}
        local = {p.stem for p in (PLUGIN / 'modules').glob('*.luau')}
        self.assertTrue(local <= set(mapped))
        for name, rel in mapped.items():
            self.assertTrue((PLUGIN / rel).is_file(), name)
        self.assertEqual(project['tree']['Main']['$path'], 'LandscapePainter.server.luau')

    def test_installer_cannot_overwrite_bridge(self):
        install = source('install.ps1')
        self.assertIn('Game1LandscapePainter.rbxmx', install)
        self.assertNotIn('Game1Bridge.rbxmx', install)
        main = source('LandscapePainter.server.luau')
        self.assertNotIn('require(script.Parent.modules.DecoManager)', main)
        self.assertIn('LandscapeAssetCatalog', main)
        self.assertIn('LandscapeProfiles', main)
        self.assertNotIn('require(script.Parent.modules.DecoAssetLoader)', main)

    def test_surface_subdivision_and_normal_guard(self):
        path = source('modules/BranchPath.luau')
        self.assertIn('remaining == 0', path)
        self.assertIn('remaining - 1', path)
        self.assertIn('stats.snapped += 1', path)
        self.assertIn('stats.missed += 1', path)
        self.assertIn('found.normal.Unit:Dot(normal) >= 0.25', path)
        logic = source('modules/BranchPlacement.luau')
        self.assertIn('outwardNormal * reach', logic)
        self.assertIn('result.Normal:Dot(outwardNormal) < 0.25', logic)
        self.assertIn('MAX_SEGMENT_LENGTH = 250', logic)
        for n in range(5):
            self.assertEqual(2 ** n, (2 ** n + 1) - 1)

    def test_preview_not_in_workspace_and_edit_only(self):
        preview = source('modules/BranchPreview.luau')
        self.assertIn('game:GetService("CoreGui")', preview)
        self.assertIn('CylinderHandleAdornment', preview)
        self.assertNotIn('self.folder.Parent = self.workspace', preview)
        main = source('LandscapePainter.server.luau')
        self.assertIn('RunService:IsRunning()', main)
        self.assertIn('Enum.KeyCode.Return', main)
        self.assertIn('Enum.KeyCode.Escape', main)
        self.assertIn('plugin.Deactivation', main)

    def test_persistent_output_only_in_recording(self):
        logic = source('modules/BranchPlacement.luau')
        self.assertLess(logic.index('TryBeginRecording'), logic.index('Instance.new("Model")'))
        self.assertIn('Enum.FinishRecordingOperation.Cancel', logic)
        self.assertIn('Enum.FinishRecordingOperation.Commit', logic)
        self.assertIn('Game1LandscapeDecor', logic)
        self.assertIn('SurfaceFollowLevel', logic)
        self.assertIn('storeAnchor(model, "Start", fromAnchor)', logic)
        self.assertIn('StrokeId', logic)


if __name__ == '__main__':
    unittest.main()
