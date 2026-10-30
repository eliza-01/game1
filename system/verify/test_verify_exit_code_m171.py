"""M171 end-to-end contract: all validator diagnostics must affect CLI exit status.

No repository files are edited: malformed inputs are injected into the in-process
read-only validation handoff in a separate Python interpreter.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
VERIFY = ROOT / "system/verify/verify.py"

# Exercise the real M54/M55 validator on altered inputs, not a mocked callback.
# The CLI and final report are executed via runpy in a child process.
_VERIFY_WITH_ALTERED_SOURCES = r'''
import runpy
import sys
from pathlib import Path

root = Path(sys.argv[1])
scenario = sys.argv[2]
sys.path.insert(0, str(root / "system/verify"))
from validators import location_asset_categories

original = location_asset_categories.check_location_asset_categories

def check_with_altered_inputs(root, report_error, *, sources, **kwargs):
    if scenario in ("m54", "combined"):
        sources = sources._replace(index_text=sources.index_text.replace(
            "filled automatically from the selected asset", "removed description hint"))
    if scenario == "m54_field":
        sources = sources._replace(index_text=sources.index_text.replace(
            'id="location-asset-publication-description"', 'id="missing-publication-description"'))
    if scenario == "m128":
        sources = sources._replace(store_text=sources.store_text.replace(
            '"prop": "Props"', '"prop": "INVALID"'))
    if scenario in ("m55", "combined"):
        sources = sources._replace(assets_js=sources.assets_js.replace(
            "decoAssetUseCategory(category);", "removed_library_category_sync();"))
    return original(root, report_error, sources=sources, **kwargs)

location_asset_categories.check_location_asset_categories = check_with_altered_inputs

if scenario == "combined":
    from validators import project_layout
    old = project_layout.check_project_identity
    def with_earlier_error(root, report_error):
        old(root, report_error)
        report_error("test earlier project identity issue")
    project_layout.check_project_identity = with_earlier_error

runpy.run_path(str(root / "system/verify/verify.py"), run_name="__main__")
'''


class VerifyExitCodeM171Tests(unittest.TestCase):
    def run_verify(self, scenario: str = "clean") -> subprocess.CompletedProcess[str]:
        command = ([sys.executable, "-X", "utf8", str(VERIFY)] if scenario == "clean" else
                   [sys.executable, "-X", "utf8", "-c", _VERIFY_WITH_ALTERED_SOURCES, str(ROOT), scenario])
        return subprocess.run(command, cwd=ROOT, text=True, capture_output=True,
                              encoding="utf-8", timeout=45, check=False)

    def test_canonical_project_reports_success_and_zero_exit(self):
        result = self.run_verify()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("verify ok · game1 m55", result.stdout)
        self.assertNotIn("verify failed", result.stdout)

    def test_m54_missing_description_hint_is_failure(self):
        result = self.run_verify("m54")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertTrue(result.stdout.startswith("verify failed\n"), result.stdout)
        self.assertIn("m54 Location Assets markup missing filled automatically from the selected asset", result.stdout)
        self.assertNotIn("verify ok", result.stdout)

    def test_m55_missing_editor_library_category_sync_is_failure(self):
        result = self.run_verify("m55")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("m55 library category must synchronize editor category", result.stdout)
        self.assertNotIn("verify ok", result.stdout)

    def test_m54_missing_description_field_is_failure(self):
        result = self.run_verify("m54_field")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('m54 Location Assets markup missing id="location-asset-publication-description"', result.stdout)
        self.assertNotIn("verify ok", result.stdout)

    def test_m128_missing_props_store_category_is_failure(self):
        result = self.run_verify("m128")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('m128 Location Assets Props integration missing "prop": "Props"', result.stdout)
        self.assertNotIn("verify ok", result.stdout)

    def test_early_and_late_errors_preserve_order_and_exit_failure(self):
        result = self.run_verify("combined")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        early = result.stdout.index("test earlier project identity issue")
        m54 = result.stdout.index("m54 Location Assets markup missing")
        m55 = result.stdout.index("m55 library category must synchronize editor category")
        self.assertLess(early, m54)
        self.assertLess(m54, m55)
        self.assertNotIn("verify ok", result.stdout)


if __name__ == "__main__":
    unittest.main()
