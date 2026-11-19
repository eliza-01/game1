"""M380: Studio, Host Agent, and UI agree on the authoritative house-sync contract."""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system' / 'control-center'))
from real_estate.studio_sync import REQUIRED_PLACED_SYNC_VERSION


class HouseSyncVersionContract(unittest.TestCase):
    def test_studio_version_matches_authoritative_server_contract(self):
        studio = (ROOT / 'system/studio-plugin/modules/StudioRealEstateModel.luau').read_text(encoding='utf-8')
        versions = re.findall(r'placedSyncVersion\s*=\s*(\d+)', studio)
        self.assertEqual(versions, [str(REQUIRED_PLACED_SYNC_VERSION)])
        self.assertEqual(REQUIRED_PLACED_SYNC_VERSION, 3)

    def test_ui_does_not_reject_successful_sync_using_a_second_version_gate(self):
        ui = (ROOT / 'system/control-center/static/real-estate.js').read_text(encoding='utf-8')
        start = ui.index('async function realEstateSync(')
        end = ui.index('async function realEstatePublish(', start)
        sync = ui[start:end]
        self.assertNotRegex(sync, r'placedSyncVersion\s*[!=]==?')
        self.assertIn('const stats=result.studio?.realEstateStats;', sync)


if __name__ == '__main__':
    unittest.main()
