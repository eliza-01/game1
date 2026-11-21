"""M405: UI reminders are informational; mutation safety is token/scan-based."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / 'system/control-center/static'


class ConfirmationRemovalM405Tests(unittest.TestCase):
    def test_registry_has_red_reminder_instead_of_checkbox(self):
        html = (STATIC / 'index.html').read_text('utf8')
        js = (STATIC / 'place-registry.js').read_text('utf8')
        css = (STATIC / 'place-registry.css').read_text('utf8')
        self.assertNotIn('id="pr-backup"', html)
        self.assertNotIn("byId('pr-backup')", js)
        self.assertIn('class="pr-backup-reminder"', html)
        self.assertIn('pr-backup-reminder{', css)
        self.assertIn('color:var(--danger)', css)
        self.assertIn('source.scan?.incomplete', js)
        self.assertIn('button.dataset.prBlocked', js)

    def test_runtime_has_one_click_build_after_preflight(self):
        html = (STATIC / 'index.html').read_text('utf8')
        js = (STATIC / 'lod-manager.js').read_text('utf8')
        backend = (ROOT / 'system/control-center/services/location_lod_manager.py').read_text('utf8')
        css = (STATIC / 'lod-manager.css').read_text('utf8')
        self.assertNotIn('id="lod-build-confirm"', html)
        self.assertNotIn('PREPARE RUNTIME', js + backend)
        self.assertIn('class="lm-backup-reminder"', html)
        self.assertIn('color:var(--danger)', css)
        self.assertIn("body:JSON.stringify({token})", js)
        self.assertIn("set(payload) != {'token'}", backend)
        self.assertIn("settings_digest(settings) != self._preflight[3]", backend)
        self.assertIn("overview['snapshot']['revisionId'] != self._preflight[2]", backend)


if __name__ == '__main__':
    unittest.main()
