"""M100: static asset freshness contract for Docker-served Asset Manager."""
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SERVER_DIR = ROOT / "system" / "control-center"


class TestAssetManagerStaticFreshness(unittest.TestCase):
    def test_prevent_stale_browser_scripts(self):
        # Handler.do_GET can be tested without opening an HTTP listener.
        with tempfile.TemporaryDirectory() as folder:
            if str(SERVER_DIR) not in sys.path:
                sys.path.insert(0, str(SERVER_DIR))
            spec = importlib.util.spec_from_file_location("m100_static_web_server", SERVER_DIR / "web_server.py")
            server = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(server)
            root = Path(folder)
            (root / "index.html").write_text("<html>test</html>", encoding="utf-8")
            (root / "monster-assets.js").write_text("const fresh=true;", encoding="utf-8")
            (root / "asset-manager.css").write_text("body { color: black; }", encoding="utf-8")
            with patch.object(server, "STATIC", root):
                for route in ("/", "/monster-assets.js?v=6", "/asset-manager.css?v=9"):
                    with self.subTest(route=route):
                        handler = object.__new__(server.Handler)
                        handler.path = route
                        handler.wfile = io.BytesIO()
                        headers = {}
                        handler.send_response = lambda code: self.assertEqual(code, 200)
                        handler.send_header = lambda k, v: headers.__setitem__(k, v)
                        handler.end_headers = lambda: None
                        handler.do_GET()
                        self.assertEqual(headers["Cache-Control"], "no-store")
                        self.assertTrue(handler.wfile.getvalue())

    def test_client_urls_and_favicon_are_explicit(self):
        html = (SERVER_DIR / "static" / "index.html").read_text(encoding="utf-8")
        self.assertIn("monster-assets.js?v=6", html)
        self.assertIn("npc-assets.js?v=3", html)
        self.assertIn('<link rel="icon" href="data:,">', html)

    def test_old_global_current_leak_does_not_return(self):
        for filename, function in (("monster-assets.js", "monsterRenderAnimationTarget"), ("npc-assets.js", "npcRenderAnimationTarget")):
            with self.subTest(filename=filename):
                script = (SERVER_DIR / "static" / filename).read_text(encoding="utf-8")
                segment = script.split(f"function {function}(){{", 1)[1].split("\n", 1)[0]
                self.assertNotIn("};const current=rows.find", segment)
                self.assertIn(";const current=rows.find", segment)


if __name__ == "__main__":
    unittest.main()
