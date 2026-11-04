"""Original M118 Studio texture sync invariants, tightened by M216."""
from pathlib import Path
from unittest import TestCase, mock
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services.studio_deco_bridge import run_deco_refresh_bridge


class LocationAssetsSyncM118(TestCase):
    def source(self, path):
        return (ROOT / path).read_text(encoding='utf-8')

    def test_legacy_unscoped_bridge_cannot_run(self):
        with self.assertRaises(TypeError):
            run_deco_refresh_bridge(timeout_seconds=1)

    def test_bridge_rejects_invalid_target_before_network(self):
        for slug in ('', 'unknown/id', 'BOGUS'):
            with self.subTest(slug=slug), self.assertRaises(ValueError):
                run_deco_refresh_bridge(timeout_seconds=1, slug=slug,
                    binding_revision=1, model_asset_id='123', atlas_asset_id='456')

    def test_no_publish_model_rebuild_or_implicit_changes_in_studio(self):
        html = self.source('system/control-center/static/index.html')
        js = self.source('system/control-center/static/deco-assets.js')
        command = self.source('system/studio-plugin/modules/StudioDecoSyncCommands.luau')
        sync = self.source('system/studio-plugin/modules/DecoPlacedAssetSync.luau')
        manager = self.source('system/studio-plugin/modules/DecoManager.luau')
        self.assertIn('id="sync-location-assets"', html)
        self.assertIn('body: JSON.stringify({slug: row.slug})', js)
        self.assertIn('schemaVersion ~= 3', command)
        self.assertIn('command.targetSlug', command)
        self.assertIn('DecoPlacedAssetSync.RefreshIds(', manager)
        self.assertIn('StudioTextureAppearance.Apply(mesh, uri, nil, true)', sync)
        for forbidden in ('LoadAssetAsync', 'previous:Destroy()', 'newModel.Parent =', ':ApplyMesh('):
            self.assertNotIn(forbidden, sync)
