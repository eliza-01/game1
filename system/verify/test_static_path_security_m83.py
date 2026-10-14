"""M83 static-publication path boundary tests (filesystem in temp sandbox)."""
from pathlib import Path
import importlib.util
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / 'system/control-center/static_paths.py'
spec = importlib.util.spec_from_file_location('game1_static_paths', MODULE)
static_paths = importlib.util.module_from_spec(spec)
spec.loader.exec_module(static_paths)


class StaticPathSecurityTests(unittest.TestCase):
    def test_serves_index_and_in_scope_files(self):
        with tempfile.TemporaryDirectory() as folder:
            static = Path(folder) / 'static'
            static.mkdir()
            (static / 'index.html').write_text('ok')
            (static / 'main.js').write_text('const ok = true;')
            self.assertTrue(static_paths.resolve_static_file(static, '/').samefile(static / 'index.html'))
            self.assertTrue(static_paths.resolve_static_file(static, '/main.js?v=4').samefile(static / 'main.js'))
            self.assertIsNone(static_paths.resolve_static_file(static, '/missing'))

    def test_rejects_raw_encoded_windows_and_symlink_traversal(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            static = root / 'static'
            static.mkdir()
            private = root / 'secret.json'
            private.write_text('secret')
            requests = ['/../secret.json', '/%2e%2e/secret.json',
                        '/%2e%2e%2fsecret.json', '/..\\secret.json', '/%00bad']
            try:
                (static / 'alias').symlink_to(private)
            except (OSError, NotImplementedError):
                pass  # Windows without developer mode may not allow symlinks.
            else:
                requests.append('/alias')
            for request in requests:
                with self.subTest(request=request):
                    self.assertIsNone(static_paths.resolve_static_file(static, request))


if __name__ == '__main__':
    unittest.main()
