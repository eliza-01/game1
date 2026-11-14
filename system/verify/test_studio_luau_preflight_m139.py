"""M139: stop the whole Studio Bridge from failing on ambiguous Luau lines."""
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / 'system/studio-plugin'
spec = importlib.util.spec_from_file_location('game1_studio_luau_preflight', PLUGIN / 'validate_luau.py')
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


class StudioLuauPreflightM139(unittest.TestCase):
    def test_real_plugin_luau_files_pass_guard(self):
        self.assertEqual(preflight.check_plugin(PLUGIN), [])

    def test_ambiguous_cast_after_clone_is_rejected(self):
        bad = ('clone = source:Clone()\n'
               '-- comment does not prevent ambiguous parse\n'
               '(clone :: Model):PivotTo(CFrame.new())\n')
        self.assertEqual(preflight.ambiguous_leading_parentheses(bad), [3])
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'modules' / 'Fail.luau'
            path.parent.mkdir()
            path.write_text(bad, encoding='utf8')
            self.assertIn('Fail.luau:3:', '\n'.join(preflight.check_plugin(Path(tmp))))

    def test_place_registry_row_separator_is_validated_before_install(self):
        inventory = (PLUGIN / 'modules/StudioPlaceRegistryInventory.luau').read_text(encoding='utf8')
        self.assertEqual(preflight.missing_place_registry_row_separator(inventory), [])
        missing = inventory.replace(
            'or (root and root:GetAttribute("Game1DecoAssetSlug")~=entry.slug),',
            'or (root and root:GetAttribute("Game1DecoAssetSlug")~=entry.slug)',
        )
        self.assertNotEqual(missing, inventory)
        self.assertEqual(len(preflight.missing_place_registry_row_separator(missing)), 1)
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'modules' / 'StudioPlaceRegistryInventory.luau'
            path.parent.mkdir()
            path.write_text(missing, encoding='utf8')
            self.assertIn('missing comma before duplicateId',
                          '\n'.join(preflight.check_plugin(Path(tmp))))

    def test_retired_collision_sync_is_not_in_plugin(self):
        # M342 intentionally removed the legacy col_mesh placement mechanism.
        manifest = (PLUGIN / 'plugin.project.json').read_text(encoding='utf8')
        self.assertNotIn('StudioRealEstatePlacedCollisionSync', manifest)
        cleanup = (PLUGIN / 'modules/StudioRetiredColMeshCleanup.luau').read_text(encoding='utf8')
        self.assertIn('function Cleanup.CleanEstate', cleanup)
        self.assertIn('function Cleanup.CleanLocation', cleanup)

    def test_install_runs_preflight_before_build_or_install(self):
        installer = (PLUGIN / 'install.ps1').read_text(encoding='utf8')
        self.assertIn("'validate_luau.py'", installer)
        self.assertLess(installer.index("'validate_luau.py'"),
                        installer.index('& $RojoExe build plugin.project.json'))
        self.assertLess(installer.index('Studio Luau preflight failed'),
                        installer.index('Install-VerifiedBundle -Source $Temp -Destination $Installed'))


if __name__ == '__main__':
    unittest.main()
