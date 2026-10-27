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

    def test_collision_sync_uses_named_clone_and_preserves_transaction(self):
        source = (PLUGIN / 'modules/StudioRealEstatePlacedCollisionSync.luau').read_text(encoding='utf8')
        self.assertIn('local staged = source:Clone()', source)
        self.assertIn('clone = staged', source)
        self.assertIn('staged:PivotTo(relative * source:GetPivot())', source)
        self.assertIn('staged.Parent = root', source)
        self.assertIn('if clone then clone:Destroy() end', source)
        self.assertIn('if old then old:Destroy() end', source)
        self.assertNotIn('(clone :: Model):PivotTo', source)

    def test_install_runs_preflight_before_build_or_install(self):
        installer = (PLUGIN / 'install.ps1').read_text(encoding='utf8')
        self.assertIn("'validate_luau.py'", installer)
        self.assertLess(installer.index("'validate_luau.py'"),
                        installer.index('rojo build plugin.project.json'))
        self.assertLess(installer.index('Studio Luau preflight failed'),
                        installer.index('Copy-Item $Temp $Installed -Force'))


if __name__ == '__main__':
    unittest.main()
