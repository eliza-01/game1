"""Regression contract for the M342R Windows / Studio cleanup correction."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
STUDIO = ROOT / "system/studio-plugin"
UI = ROOT / "system/control-center/static"


class ColCleanupRegression(unittest.TestCase):
    def text(self, base, file):
        return (base / file).read_text(encoding="utf8")

    def test_place_registry_has_no_col_dependency(self):
        inventory = self.text(STUDIO, "modules/StudioPlaceRegistryInventory.luau")
        for old in ('Нет обязательного COL-меша', 'RequiresCollider(', 'needsCol=', 'colCount='):
            self.assertNotIn(old, inventory)
        self.assertNotIn('RequiresCollider(', self.text(STUDIO, 'modules/StudioLocationPublishedGeometry.luau'))

    def test_ui_has_no_stale_col_badge(self):
        self.assertNotIn('COL-меш не найден', self.text(UI, 'location-asset-workflow.js'))
        self.assertNotIn('Восстановлено COL', self.text(UI, 'place-registry.js'))

    def test_untagged_scene_cleanup(self):
        boot = self.text(STUDIO, 'Game1Bridge.server.luau')
        cleanup = self.text(STUDIO, 'modules/StudioRetiredColMeshCleanup.luau')
        self.assertIn('function Cleanup.CleanLegacyAssetTree', cleanup)
        for folder in ('Places', 'Plots'):
            self.assertIn(f'CleanLegacyAssetTree(Workspace:FindFirstChild("{folder}"))', boot)
        self.assertIn('CleanLegacyAssetTree(ServerStorage)', boot)

    def test_clone_cleaned_before_rig_validation(self):
        code = self.text(STUDIO, 'modules/DecoAssetLoader.luau')
        self.assertLess(code.index('RetiredCleanup.CleanLocation(model)'), code.index('Carrier.Validate(model, row.rigManifest'))

    def test_test_case_closes_windows_sqlite_handles(self):
        code = self.text(ROOT / 'system/verify', 'test_col_mesh_retirement_m342.py')
        self.assertIn('closing(sqlite3.connect(rdb))', code)
        self.assertIn('closing(sqlite3.connect(ldb))', code)


if __name__ == '__main__':
    unittest.main()
