"""M442: strict shared time/radius tuning without touching live project files."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import sys
import unittest
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from mechanics import settings
from api import mechanics
from api.write_dispatch import dispatch_post


class FireplaceTuningM442(unittest.TestCase):
    def test_defaults_match_generated_luau_and_shared_contract(self):
        values = settings.load()
        self.assertEqual(settings.OUTPUT.read_text(encoding='utf-8'), settings.render_luau(values))
        self.assertEqual(values['FuelDurationSeconds'], 120)
        self.assertEqual(values['EmbersDurationSeconds'], 120)
        self.assertEqual(values['CookingSecondsOnFire'], 30)
        self.assertEqual(values['CookingSecondsOnEmbers'], 60)
        self.assertEqual(values['ProgressVisibleRadius'], 50)
        self.assertEqual(values['CampfireDurationSeconds'], 120)
        lua = (ROOT / 'src/shared/world/FireplaceMechanicsConfig.luau').read_text(encoding='utf-8')
        for field in settings.FIELD_LIMITS:
            self.assertIn(f'{field} = Tuning.{field}', lua)

    def test_no_unexpected_or_invalid_values(self):
        original = settings.load()
        invalid = [dict(original, Surprise=1),
                   dict(original, FuelDurationSeconds=0),
                   dict(original, CookingSecondsOnFire=float('nan')),
                   dict(original, CookingSecondsOnFire=2.5),
                   dict(original, CampfireAimRadius=99),
                   dict(original, CampfireInteractionRadius=1),
                   dict(original, CampfireAimRadius=9, CampfireInteractionRadius=6)]
        for item in invalid:
            with self.subTest(item=item), self.assertRaises(ValueError):
                settings.validate(item)

    def test_atomic_save_and_revision_conflict_through_api(self):
        with TemporaryDirectory() as temp:
            path = Path(temp)
            source = path / 'fireplace.json'
            output = path / 'FireplaceMechanicsTuning.luau'
            source.write_text(json.dumps(settings.load()), encoding='utf-8')
            output.write_text(settings.render_luau(settings.load()), encoding='utf-8')
            with patch.object(settings, 'SOURCE', source), patch.object(settings, 'OUTPUT', output):
                status, payload = mechanics.route(urlparse('/api/mechanics/fireplace-settings'))
                self.assertEqual(status, 200)
                old = payload['settings']
                new = dict(old, CampfireDurationSeconds=132)
                status, response = dispatch_post('/api/mechanics/fireplace-settings',
                    lambda: {'expected': old, 'settings': new}, {})
                self.assertEqual(status, 200)
                self.assertTrue(response['studioSyncRequired'])
                self.assertEqual(settings.load(), new)
                self.assertEqual(output.read_text(), settings.render_luau(new))
                status, response = dispatch_post('/api/mechanics/fireplace-settings',
                    lambda: {'expected': old, 'settings': old}, {})
                self.assertEqual(status, 409)
                self.assertIn('changed elsewhere', response['error'])
                self.assertEqual(settings.load(), new)

    def test_ui_has_edit_mode_only_for_fireplace(self):
        ui = (ROOT / 'system/control-center/static/mechanics.js').read_text(encoding='utf-8')
        css = (ROOT / 'system/control-center/static/mechanics.css').read_text(encoding='utf-8')
        self.assertIn("item.id === 'fireplace' ? [['settings','Настройки']]", ui)
        self.assertIn("'/api/mechanics/fireplace-settings'", ui)
        self.assertIn('form.addEventListener(\'submit\'', ui)
        self.assertIn('state.fireplaceSettings', ui)
        self.assertIn('expected:state.fireplaceSettings', ui)
        self.assertIn('Studio Sync', ui)
        self.assertIn('.mx-setting-grid', css)


if __name__ == '__main__':
    unittest.main()
