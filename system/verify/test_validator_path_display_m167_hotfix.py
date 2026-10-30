"""Cross-platform regression coverage for validator diagnostic paths."""

from pathlib import PurePosixPath, PureWindowsPath, Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "system/verify"))
from validators.path_display import project_relative_path


class ValidatorPathDisplayTests(unittest.TestCase):
    def test_windows_paths_use_forward_slashes(self):
        root = PureWindowsPath(r"E:\RobloxProjects\game1")
        path = root / "system" / "control-center" / "monster_store.py"
        self.assertEqual(
            project_relative_path(path, root),
            "system/control-center/monster_store.py",
        )

    def test_posix_paths_use_forward_slashes(self):
        root = PurePosixPath("/home/game1")
        path = root / "src" / "client" / "check.luau"
        self.assertEqual(project_relative_path(path, root), "src/client/check.luau")


if __name__ == "__main__":
    unittest.main()
