"""M395: LandscapePainter Material+Color transition uses saved appearance and auditable Sync."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services.place_registry.catalog import build_catalog


def source(path):
    return (ROOT / path).read_text(encoding='utf-8')


class _FakeLocation:
    def __init__(self, mode):
        self.mode = mode

    def snapshot(self):
        return {'items': [{
            'slug': 'lantern_03', 'status': 'PUBLISHED',
            'model_asset_id': '131393276771930',
            'texture_asset_id': '120115686826246' if self.mode != 'material' else None,
            'appearanceMode': self.mode,
            'visualMaterial': 'SmoothPlastic', 'visualColor': '#FFFFFF',
            'alphaEnabled': False, 'meshOptions': {},
        }]}

    def model_publication_ids(self, slug):
        return ['131393276771930']

    def mesh_id_inventory(self, slug):
        return [{'modelAssetId': '131393276771930', 'meshes': [
            {'meshId': '135910285016894', 'count': 1, 'visualNames': ['lantern_03']},
        ]}]

    def aliases_for(self, slug):
        return []

    def rig_manifest(self, slug, model):
        return {'structuralHash': 'rig'}


class PainterMaterialSyncContract(unittest.TestCase):
    def test_catalog_reflects_material_mode_without_requiring_new_atlas(self):
        atlas = build_catalog(_FakeLocation('atlas'))
        material = build_catalog(_FakeLocation('material'))
        self.assertNotEqual(atlas['digest'], material['digest'])
        self.assertEqual(material['items'][0]['appearanceMode'], 'material')
        self.assertEqual(material['items'][0]['atlasAssetId'], '')
        self.assertEqual(material['items'][0]['modelAssetId'], '131393276771930')

    def test_scan_is_invalidated_by_mode_color_and_per_mesh_options(self):
        ui = source('system/control-center/static/location-asset-workflow.js')
        self.assertIn('const appearanceSignature=item=>JSON.stringify([', ui)
        self.assertIn("item?.meshOptions||{}", ui)
        self.assertIn('preview.appearanceSignature===appearanceSignature(item)', ui)
        self.assertIn('state.scanStale=true;', ui)
        self.assertIn('state.scan.appearanceSignature===appearanceSignature(item)', ui)
        self.assertIn('if(!ensureSavedModelForSync())return;', ui)
        self.assertIn('Model · FBX → Apply Changes', ui)

    def test_external_sync_uses_shared_visual_and_rechecks_actual_studio_properties(self):
        sync = source('system/studio-plugin/modules/StudioPlaceRegistrySync.luau')
        ui = source('system/control-center/static/location-asset-workflow.js')
        texture = source('system/studio-plugin/modules/StudioTextureAppearance.luau')
        visual = source('system/studio-plugin/modules/StudioLocationVisualAppearance.luau')
        self.assertIn('if item.external then', sync)
        self.assertIn('Visual.Apply(snapshot.mesh,row)', sync)
        self.assertIn('Visual.AssertCurrent(snapshot.mesh,row)', sync)
        self.assertIn('PainterIntegrity.AssertUnchanged(ref.integrity)', sync)
        self.assertIn('StudioTextureAppearance.ApplyMaterial(mesh,', texture)
        self.assertIn('mesh.TextureID=""', texture)
        self.assertIn('removeSurfaces(mesh)', texture)
        self.assertIn('if mode=="material" then', visual)
        self.assertIn('Texture.ApplyVisual(mesh,row)', visual)
        self.assertIn("const audit=(await request('/api/location-place-registry'", ui)
        self.assertIn('p.review||p.needsTexture||p.needsOwnerCleanup', ui)

    def test_effective_mesh_override_is_exposed_in_find(self):
        scan = source('system/studio-plugin/modules/StudioPublishedMeshHistory.luau')
        ui = source('system/control-center/static/location-asset-workflow.js')
        self.assertIn('effectiveAppearanceMode=tostring(settings.appearanceMode or "atlas")', scan)
        self.assertIn('appearanceOverride=typeof(row.meshOptions)=="table"', scan)
        self.assertIn('p.effectiveAppearanceMode', ui)
        self.assertIn('MeshPart override', ui)


if __name__ == '__main__':
    unittest.main()
