"""M253: Deco Manager and Location Assets share one refreshed registry selection."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class DecoLocationRegistryCoherenceM253(unittest.TestCase):
    def test_find_and_sync_refresh_exact_target_preview(self):
        source = (ROOT / 'system/studio-plugin/modules/DecoManager.luau').read_text(
            encoding='utf-8'
        )
        self.assertIn('function DecoManager:_showSlug(slug: string): boolean', source)
        self.assertIn('self.registry=registry', source)
        self.assertIn('if self.widget.Enabled then self:_showSlug(slug) end', source)
        self.assertIn('local selectedSlug = targetSlug or (self.currentRow and', source)
        self.assertIn('not self:_showSlug(selectedSlug)', source)

    def test_browser_refreshes_location_assets_before_post_sync_find(self):
        source = (ROOT / 'system/control-center/static/location-asset-workflow.js').read_text(
            encoding='utf-8'
        )
        success = source.split('const summary=window.game1StudioSync.locationSummary', 1)[1]
        self.assertLess(success.index('await decoAssetLoad();'),
                        success.index('await refreshSyncReport();'))


if __name__ == '__main__':
    unittest.main()
