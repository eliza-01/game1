"""M226: the Studio plugin installer must fail safely when Windows locks a bundle."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "system/studio-plugin/install.ps1"


class StudioPluginInstallerLockM226(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = INSTALLER.read_text(encoding="utf-8")

    def test_verified_build_before_publishing_either_destination(self):
        source = self.script
        self.assertIn("if($LASTEXITCODE -ne 0){throw 'Rojo Studio plugin build failed", source)
        self.assertIn("$BuiltHash=(Get-FileHash -LiteralPath $Temp", source)
        self.assertLess(source.index("$BuiltHash="), source.index("Install-VerifiedBundle -Source $Temp -Destination $Generated"))
        self.assertLess(source.index("Install-VerifiedBundle -Source $Temp -Destination $Generated"),
                        source.index("Install-VerifiedBundle -Source $Temp -Destination $Installed"))

    def test_copy_is_checked_and_retried_not_silently_ignored(self):
        source = self.script
        self.assertIn("function Install-VerifiedBundle", source)
        self.assertIn("$MaxAttempts=5", source)
        self.assertIn("Copy-Item -LiteralPath $Source -Destination $Destination -Force -ErrorAction Stop", source)
        self.assertIn("Start-Sleep -Milliseconds (200 * $Attempt)", source)
        self.assertIn("Studio bridge install failed:", source)
        self.assertIn("run ONLY system/studio-plugin/install.ps1 again", source)

    def test_matching_build_is_skipped_and_final_hash_verified(self):
        source = self.script
        self.assertIn("if($ExistingHash -eq $ExpectedHash)", source)
        self.assertIn("if($GeneratedHash -ne $InstalledHash -or $GeneratedHash -ne $BuiltHash)", source)
        self.assertNotIn("Remove-Item $Generated", source)
        self.assertNotIn("Remove-Item $Installed", source)


if __name__ == "__main__":
    unittest.main()
