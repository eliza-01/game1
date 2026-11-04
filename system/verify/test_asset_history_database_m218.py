"""M218 executable browser navigation/copy/render checks, independent of MySQL."""
from pathlib import Path
import shutil
import subprocess
import unittest


class DatabaseHistoryUiM218(unittest.TestCase):
    def test_browser_history_behavior(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node.js not installed')
        root = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            [node, str(root / 'system/verify/asset_history_database_m218.js')],
            cwd=root, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('21 checks OK', result.stdout)


if __name__ == '__main__':
    unittest.main()
