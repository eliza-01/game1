"""M382: third visual mode, shared Studio binder, atlas identity and runtime parity."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from location_asset_store import LocationAssetStore
from real_estate.store import mesh_options
from real_estate.studio_sync import RealEstateStudioSync
from services import mesh_visual_appearance as appearance
from services.place_registry.catalog import build_catalog
from services.studio_deco_bridge import run_deco_refresh_bridge


class MaterialAtlasContract(unittest.TestCase):
    def test_three_modes_keep_old_defaults_and_validate_combined(self):
        self.assertEqual(appearance.validated('material_atlas', 'WoodPlanks', '#f0a011'),
                         ('material_atlas', 'WoodPlanks', '#F0A011'))
        self.assertTrue(appearance.uses_atlas('material_atlas'))
        self.assertTrue(appearance.uses_material('material_atlas'))
        self.assertFalse(appearance.uses_atlas('material'))
        self.assertFalse(appearance.uses_material('atlas'))
        with self.assertRaises(ValueError):
            appearance.validated('material', 'ForceField', '#FFFFFF')
        self.assertEqual(appearance.validated('material_atlas', 'ForceField', '#FFFFFF')[1], 'ForceField')
        with self.assertRaises(ValueError):
            appearance.validated('material_with_atlas', 'Wood', '#FFFFFF')
        self.assertEqual(mesh_options(('roof',), None)['roof']['appearanceMode'], 'material')
        self.assertEqual(mesh_options(('roof',), None, ('roof',))['roof']['appearanceMode'], 'atlas')

    def test_house_combined_is_part_scoped_and_alpha_explicit(self):
        options = mesh_options(('roof', 'plants'), {
            'roof': {'appearanceMode': 'material_atlas', 'visualMaterial': 'Slate',
                     'visualColor': '#acd012', 'alphaEnabled': False},
            'plants': {'appearanceMode': 'material_atlas', 'visualMaterial': 'ForceField',
                       'visualColor': '#FFFFFF', 'alphaEnabled': True},
        })
        self.assertEqual(options['roof']['visualColor'], '#ACD012')
        self.assertTrue(options['plants']['alphaEnabled'])
        self.assertFalse(options['roof']['alphaEnabled'])
        with self.assertRaisesRegex(ValueError, 'requires an atlas'):
            mesh_options(('roof',), {'roof': {'appearanceMode': 'material', 'alphaEnabled': True}})

    def _registered(self, folder: Path) -> tuple[LocationAssetStore, dict, dict]:
        source = folder / 'location.fbx'
        source.write_bytes(b'FBX test fixture')
        png = folder / 'house_decal_4x4_atlas.png'
        Image.new('RGBA', (4, 4), (255, 255, 255, 255)).save(png)
        store = LocationAssetStore(folder)
        row = store.register({
            'nameEn': 'Material Atlas', 'slug': 'material_atlas_01', 'category': 'prop',
            'modelSourcePath': str(source), 'textureSourcePath': str(png),
            'appearanceMode': 'material_atlas', 'visualMaterial': 'WoodPlanks',
            'visualColor': '#C8BFA0', 'alphaEnabled': True,
        })
        return store, row, store.atlases.get_variant(row['atlasVariantId'])

    def test_location_registration_publication_catalog_and_export(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store, row, variant = self._registered(root)
            self.assertEqual(row['appearanceMode'], 'material_atlas')
            self.assertEqual(row['visualMaterial'], 'WoodPlanks')
            self.assertTrue(row['alphaEnabled'])
            self.assertEqual(row['atlasVariantId'], variant['id'])
            self.assertEqual(store.atlases.binding('location_asset', row['slug'])['variant_id'], variant['id'])
            with store.atlases.connect() as db:
                db.execute('UPDATE texture_atlas_variants SET published_id=?,published_sha256=source_sha256 WHERE id=?',
                           ('123456789', variant['id']))
            with store.connect() as db:
                db.execute('UPDATE location_assets SET model_asset_id=?,model_published_sha256=model_sha256 WHERE slug=?',
                           ('987654321', row['slug']))
            store.export()
            published = store.get(row['slug'])
            self.assertEqual(published['status'], 'PUBLISHED')
            self.assertEqual(str(published['texture_asset_id']), '123456789')
            catalog = build_catalog(store)['items']
            self.assertEqual(len(catalog), 1)
            self.assertEqual(catalog[0]['appearanceMode'], 'material_atlas')
            self.assertEqual(catalog[0]['atlasAssetId'], '123456789')
            self.assertEqual(catalog[0]['robloxMaterial'], 'WoodPlanks')
            manifest = (root / 'src/shared/world/LocationAssetRegistry.luau').read_text(encoding='utf-8')
            self.assertIn('appearanceMode = "material_atlas"', manifest)
            self.assertIn('visualMaterial = "WoodPlanks"', manifest)
            self.assertIn('textureAssetId = "123456789"', manifest)
            self.assertIn('alphaEnabled = true', manifest)
            # Saving only a material/color edit must preserve atlas identity.
            changed = store.register({
                'nameEn': 'Material Atlas', 'slug': row['slug'], 'category': 'prop',
                'appearanceMode': 'material_atlas', 'visualMaterial': 'Slate',
                'visualColor': '#8A9099',
            })
            self.assertEqual(changed['atlasVariantId'], variant['id'])
            self.assertEqual(changed['visualMaterial'], 'Slate')
            self.assertEqual(str(changed['texture_asset_id']), '123456789')

    def test_house_studio_sync_sends_image_and_material_together(self):
        bone={'name':'houseplant_01','parent':'','matrixLocal':[0]*16}
        mesh={'name':'roof','armature':'house_armature', 'bones':[bone],
              'influencedBones':[],'authoredPlacement':{'version':3,'centerInPivot':[0,0,0],'size':[1,1,1]}}
        row={'slug':'house_level5_01','house_level':5,'purchase_price':10,
             'min_level':1,'sale_price':5,'status':'PUBLISHED','meshParts':['roof'],
             'skeleton':{'meshes':[mesh]},
             'rigAssets':{'rig_carrier':{'assetId':'100','publishedSha256':'hash'},
                          'roof':{'assetId':'101','publishedSha256':'hash'}},
             'rigPublicationHashes':{'rig_carrier':'hash','roof':'hash'},
             'textures':{'roof':{'assetId':'123456789','path':'','atlasVariantId':None}},
             'meshOptions':mesh_options(('roof',), {'roof':{'appearanceMode':'material_atlas',
                 'visualMaterial':'Slate','visualColor':'#A1B2C3','alphaEnabled':True}})}
        captured=[]
        def load_model(asset_id, args, **kwargs):
            captured.append(kwargs['metadata'])
            return {'realEstateStats':{'bonesValidated':True,'rigsValidated':2,
                'texturesApplied':1,'placedSyncVersion':3}}
        RealEstateStudioSync(SimpleNamespace(root=Path('/'),get=lambda _:row), load_model).sync(row['slug'])
        manifest=captured[0]
        self.assertEqual([part['slot'] for part in manifest['textures']], ['roof'])
        self.assertEqual(manifest['meshOptions']['roof']['appearanceMode'],'material_atlas')
        self.assertEqual(manifest['meshOptions']['roof']['visualMaterial'],'Slate')
        self.assertTrue(manifest['meshOptions']['roof']['alphaEnabled'])

    def test_studio_sync_requires_image_for_combined_mode(self):
        args = dict(slug='material_atlas_01', binding_revision=1,
                    model_asset_id='987654321', atlas_asset_id='123456789',
                    appearance_mode='material_atlas', phase='invalid')
        with self.assertRaisesRegex(ValueError, 'phase'):
            run_deco_refresh_bridge(**args)
        with self.assertRaisesRegex(ValueError, 'Image Asset ID'):
            run_deco_refresh_bridge(**{**args, 'atlas_asset_id': ''})

    def test_studio_and_editors_share_three_mode_contract(self):
        shared=(ROOT/'system/studio-plugin/modules/StudioTextureAppearance.luau').read_text(encoding='utf-8')
        location=(ROOT/'system/studio-plugin/modules/StudioLocationVisualAppearance.luau').read_text(encoding='utf-8')
        house=(ROOT/'system/studio-plugin/modules/StudioRealEstateAppearance.luau').read_text(encoding='utf-8')
        runtime=(ROOT/'src/server/world/EnvironmentAssetVisuals.luau').read_text(encoding='utf-8')
        streamer=(ROOT/'src/client/world/LocationWorldStreamer.luau').read_text(encoding='utf-8')
        html=(ROOT/'system/control-center/static/index.html').read_text(encoding='utf-8')
        estate=(ROOT/'system/control-center/static/real-estate.js').read_text(encoding='utf-8')
        editor=(ROOT/'system/control-center/static/location-asset-workflow.js').read_text(encoding='utf-8')
        self.assertIn('mode=="material_atlas"', shared)
        self.assertIn('StudioTextureAppearance.ApplyLocation(mesh,uri,opts.alphaEnabled==true)', shared)
        self.assertIn('Texture.ApplyVisual(mesh,row', location)
        self.assertIn('Texture.ApplyVisual(mesh,settings', house)
        self.assertIn('"material_atlas"', runtime)
        self.assertIn('"material_atlas"', streamer)
        for text in (html,estate,editor):
            self.assertIn('value="material_atlas"', text)

if __name__ == '__main__':
    unittest.main()
