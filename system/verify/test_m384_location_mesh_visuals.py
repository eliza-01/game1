"""M384 · Location Asset MeshPart visuals share the existing Registry and physics authoring."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'system/control-center'))
from location_asset_store import LocationAssetStore
from services.mesh_authoring_policy import normalize_location_options
from services.place_registry.catalog import build_catalog


ANALYSIS = {'meshes': [
    {'name':'stone', 'vertices':12, 'bones':[]},
    {'name':'foliage','vertices':24,'bones':[]},
    {'name':'rig_carrier','vertices':0,'bones':[]},
], 'armatures':[], 'unassignedArmatures':[], 'hasCollider':False}


class M384LocationMeshVisuals(TestCase):
    def test_visual_overrides_are_validated_without_changing_physics_defaults(self):
        options = normalize_location_options(ANALYSIS, {'foliage': {
            'glass': True, 'noCollide': True, 'collisionFidelity': 'Hull',
            'appearanceMode': 'material_atlas', 'visualMaterial': 'LeafyGrass',
            'visualColor': '#aabbcc', 'alphaEnabled': True, 'atlasVariantId': 25,
        }, 'stone': {'appearanceMode':'material','visualMaterial':'Granite',
                     'visualColor':'#987654'}})
        self.assertEqual(options['foliage']['visualColor'], '#AABBCC')
        self.assertEqual(options['foliage']['collisionFidelity'], 'Hull')
        self.assertEqual(options['foliage']['atlasVariantId'], 25)
        self.assertNotIn('appearanceMode', options['rig_carrier'] if 'rig_carrier' in options else {})
        self.assertNotIn('rig_carrier', options)
        for invalid in (
            {'stone':{'appearanceMode':'material','atlasVariantId':25}},
            {'stone':{'appearanceMode':'atlas','texture_asset_id':'123'}},
            {'stone':{'appearanceMode':'material','visualMaterial':'Water'}},
            {'stone':{'appearanceMode':'material','alphaEnabled':'true'}},
            {'stone':{'appearanceMode':'atlas','atlasVariantId':True}},
            {'ghost':{'appearanceMode':'material'}},
        ):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                normalize_location_options(ANALYSIS,invalid)

    def test_registration_revision_publication_and_runtime_export(self):
        with TemporaryDirectory() as folder:
            root=Path(folder)
            fbx=root/'asset.fbx';fbx.write_bytes(b'test FBX inspected with mocked Blender result')
            atlas_file=root/'leaves_16x16_atlas.png'
            Image.new('RGBA',(16,16),(20,180,40,128)).save(atlas_file)
            store=LocationAssetStore(root)
            variant=store.atlases.adopt_file(str(atlas_file))
            options={'stone':{'appearanceMode':'material','visualMaterial':'Granite',
                              'visualColor':'#123456'},
                     'foliage':{'appearanceMode':'material_atlas','visualMaterial':'LeafyGrass',
                                'visualColor':'#AABBCC','alphaEnabled':True,
                                'atlasVariantId':int(variant['id'])}}
            with patch('location_asset_store.inspect_location_fbx',return_value=ANALYSIS):
                registered=store.register({'nameEn':'Mixed Mesh','slug':'mixed_mesh',
                    'category':'prop','appearanceMode':'material','visualMaterial':'Plastic',
                    'visualColor':'#FFFFFF','modelSourcePath':str(fbx),
                    'inspectFbx':True,'meshOptions':options})
            self.assertEqual(registered['meshOptions']['stone']['visualMaterial'],'Granite')
            self.assertFalse(registered['meshOptions']['foliage']['texture_asset_id'])
            with store.connect() as db:
                db.execute("UPDATE location_assets SET model_asset_id='123456',model_published_sha256=model_sha256 WHERE slug='mixed_mesh'")
            self.assertNotEqual(store.get('mixed_mesh')['status'],'PUBLISHED')
            with store.connect() as db:
                db.execute("UPDATE texture_atlas_variants SET published_id='998877',published_sha256=source_sha256 WHERE id=?",(variant['id'],))
            store.export()
            published=store.get('mixed_mesh')
            self.assertEqual(published['status'],'PUBLISHED')
            self.assertEqual(published['meshOptions']['foliage']['texture_asset_id'],'998877')
            self.assertIsNone(published['texture_asset_id'])
            self.assertEqual(build_catalog(store)['items'][0]['meshOptions']['foliage']['texture_asset_id'],'998877')
            registry=(root/'src/shared/world/LocationAssetRegistry.luau').read_text(encoding='utf-8')
            self.assertIn('["texture_asset_id"]="998877"',registry)
            with self.assertRaisesRegex(ValueError,'rebind this MeshPart'):
                store.atlases.retirement_plan(variant['id'])
            # A new saved revision can change only one MeshPart's look without new FBX publication.
            changed=store.register({'slug':'mixed_mesh','nameEn':'Mixed Mesh','category':'prop',
                'appearanceMode':'material','visualMaterial':'Plastic','visualColor':'#FFFFFF',
                'meshOptions':{'stone':options['stone'],'foliage':{
                  'appearanceMode':'material','visualMaterial':'Grass','visualColor':'#008800'}}})
            self.assertNotIn('atlasVariantId',changed['meshOptions']['foliage'])
            self.assertEqual(changed['model_asset_id'],'123456')
            self.assertEqual(changed['status'],'PUBLISHED')
            self.assertIsNotNone(store.atlases.retirement_plan(variant['id']))

    def test_independent_file_atlas_is_registered_on_new_asset(self):
        with TemporaryDirectory() as folder:
            root=Path(folder)
            fbx=root/'rock_tree.fbx';fbx.write_bytes(b'mocked FBX')
            image=root/'foliage_16x16_atlas.png'
            Image.new('RGBA',(16,16),(10,30,20,150)).save(image)
            store=LocationAssetStore(root)
            with patch('location_asset_store.inspect_location_fbx',return_value=ANALYSIS):
                registered=store.register({'nameEn':'Rock Tree','slug':'rock_tree',
                    'category':'tree','modelSourcePath':str(fbx),'inspectFbx':True,
                    'appearanceMode':'material','meshOptions':{
                        'stone':{'appearanceMode':'material','visualMaterial':'Rock',
                                 'visualColor':'#C0C0C0'},
                        'foliage':{'appearanceMode':'atlas','alphaEnabled':True,
                                   'textureSourcePath':str(image)}}})
            self.assertIsNone(registered['texture_asset_id'])
            self.assertNotIn('textureSourcePath',registered['meshOptions']['foliage'])
            variant_id=registered['meshOptions']['foliage']['atlasVariantId']
            self.assertGreater(variant_id,0)
            variant=store.atlases.get_variant(variant_id)
            self.assertEqual(variant['filename'],'foliage_16x16_atlas.png')
            self.assertEqual(registered['meshOptions']['stone']['visualMaterial'],'Rock')

    def test_missing_per_mesh_atlas_fails_closed(self):
        with TemporaryDirectory() as folder:
            root=Path(folder);fbx=root/'tree.fbx';fbx.write_bytes(b'mock')
            store=LocationAssetStore(root)
            with patch('location_asset_store.inspect_location_fbx',return_value=ANALYSIS):
                with self.assertRaisesRegex(ValueError,'select an Atlas Registry variant'):
                    store.register({'nameEn':'Tree','slug':'tree','category':'tree',
                        'appearanceMode':'material','modelSourcePath':str(fbx),'inspectFbx':True,
                        'meshOptions':{'foliage':{'appearanceMode':'atlas'}}})

    def test_editors_scan_and_runtime_all_consume_the_same_mesh_contract(self):
        sources={p:(ROOT/p).read_text(encoding='utf-8') for p in (
            'system/control-center/static/deco-assets.js',
            'system/control-center/static/location-asset-workflow.js',
            'system/control-center/static/mesh-authoring.js',
            'system/studio-plugin/modules/StudioPublishedMeshHistory.luau',
            'system/studio-plugin/modules/StudioPlaceRegistryInventory.luau',
            'system/studio-plugin/modules/StudioLocationVisualAppearance.luau',
            'src/server/world/EnvironmentAssetVisuals.luau',
            'src/client/world/LocationWorldStreamer.luau')}
        self.assertIn('game1MeshAuthoring.inspectionView',sources['system/control-center/static/deco-assets.js'])
        self.assertIn('game1MeshAuthoring.inspectionView',sources['system/control-center/static/location-asset-workflow.js'])
        self.assertIn('data-mesh-visual="atlasVariantId"',sources['system/control-center/static/mesh-authoring.js'])
        self.assertIn('Visual.Settings(part,row)',sources['system/studio-plugin/modules/StudioPublishedMeshHistory.luau'])
        self.assertIn('Visual.Settings(visualPart',sources['system/studio-plugin/modules/StudioPlaceRegistryInventory.luau'])
        self.assertIn('row.meshOptions[mesh.Name]',sources['system/studio-plugin/modules/StudioLocationVisualAppearance.luau'])
        self.assertIn('definition.meshOptions[mesh.Name]',sources['src/server/world/EnvironmentAssetVisuals.luau'])
        self.assertIn('asset.meshOptions[mesh.Name]',sources['src/client/world/LocationWorldStreamer.luau'])
