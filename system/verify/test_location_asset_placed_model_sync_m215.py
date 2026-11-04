"""M215 destructive behaviour is permanently retired by M216.

Keep a dedicated guard here so an apparently harmless future refactor cannot
re-introduce the cloned Model replacement that moved placed decorations.
"""
from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]


class M215Retirement(TestCase):
    def test_no_model_replacement_in_location_sync(self):
        sync = (ROOT / 'system/studio-plugin/modules/DecoPlacedAssetSync.luau').read_text(encoding='utf-8')
        manager = (ROOT / 'system/studio-plugin/modules/DecoManager.luau').read_text(encoding='utf-8')
        self.assertIn('function DecoPlacedAssetSync.RefreshIds(', sync)
        self.assertIn('DecoPlacedAssetSync.RefreshIds(', manager)
        self.assertNotIn('function DecoPlacedAssetSync.RefreshModels(', sync)
        self.assertNotIn('DecoPlacedAssetSync.RefreshModels(', manager)
        for unsafe in ('previous:Destroy()', 'newModel.Parent =', 'templates[item.slug]', 'model:Destroy()'):
            self.assertNotIn(unsafe, sync)

    def test_fbx_revision_stamped_only_after_geometry_update(self):
        sync = (ROOT / 'system/studio-plugin/modules/DecoPlacedAssetSync.luau').read_text(encoding='utf-8')
        refresh = sync.split('function DecoPlacedAssetSync.RefreshIds(', 1)[1]
        self.assertIn('Game1DecoRegistryModelAssetId', sync)
        self.assertIn('Game1DecoPublishedModelSha256', sync)
        self.assertIn('pendingGeometry', sync)
        self.assertIn('RigSwap.Commit(item.swap)', refresh)
        self.assertLess(refresh.index('RigSwap.Commit(item.swap)'),
                        refresh.index('model:SetAttribute("Game1DecoPublishedModelSha256", publishedSha)'))

    def test_fresh_placement_is_stamped_before_it_enters_workspace(self):
        sync = (ROOT / 'system/studio-plugin/modules/DecoPlacedAssetSync.luau').read_text(encoding='utf-8')
        placement = (ROOT / 'system/studio-plugin/modules/DecoPlacement.luau').read_text(encoding='utf-8')
        stamp = sync.split('function DecoPlacedAssetSync.StampPublishedModel(', 1)[1].split(
            'function DecoPlacedAssetSync.RefreshIds(', 1)[0]
        self.assertIn('model.Parent ~= nil', stamp)
        self.assertIn('SetAttribute("Game1DecoPublishedModelAssetId"', stamp)
        self.assertIn('SetAttribute("Game1DecoPublishedModelSha256"', stamp)
        self.assertIn('SetAttribute(REFERENCE', stamp)
        self.assertLess(placement.index('DecoPlacedAssetSync.StampPublishedModel(placed, row)'),
                        placement.index('placed.Parent ='))
