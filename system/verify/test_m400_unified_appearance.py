"""M400 · authored two-mode Appearance / legacy atlas read / shared variant preservation."""
from __future__ import annotations
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'system/control-center'))
from location_asset_store import LocationAssetStore
from services.mesh_visual_appearance import validated,BASEPART_MATERIALS

ANALYSIS={'meshes':[{'name':'metal','vertices':12,'bones':[]},
                   {'name':'glass','vertices':12,'bones':[]},
                   {'name':'rig_carrier','vertices':0,'bones':[]}],
          'armatures':[],'unassignedArmatures':[],'hasCollider':False}

class M400Appearance(unittest.TestCase):
    def test_default_is_plastic_but_smooth_plastic_is_still_supported(self):
        self.assertEqual(validated('material',None,None),('material','Plastic','#FFFFFF'))
        self.assertIn('SmoothPlastic',BASEPART_MATERIALS)
        with TemporaryDirectory() as folder:
            store=LocationAssetStore(Path(folder))
            # Raw SQL with no mode is a historic atlas record: the immutable
            # schema default must remain readable by the M203 migration.
            with store.connect() as db:
                db.execute("INSERT INTO location_assets(slug,name_en,category,model_path,revision,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                           ('legacy_raw','Legacy','prop','',1,1,1))
            self.assertEqual(store.get('legacy_raw')['appearanceMode'],'atlas')
            self.assertEqual(store.get('legacy_raw')['visualMaterial'],'Plastic')
            # Authoring through the modern API starts with Material + Color.
            from unittest.mock import patch
            fbx=Path(folder)/'new.fbx';fbx.write_bytes(b'fixture')
            with patch('location_asset_store.inspect_location_fbx',return_value=ANALYSIS):
                created=store.register({'slug':'new_asset','nameEn':'New','category':'prop',
                                        'modelSourcePath':str(fbx),'inspectFbx':True})
            self.assertEqual(created['appearanceMode'],'material')
            self.assertEqual(created['visualMaterial'],'Plastic')

    def test_legacy_atlas_is_readable_without_rewriting_publication(self):
        with TemporaryDirectory() as folder:
            store=LocationAssetStore(Path(folder))
            with store.connect() as db:
                db.execute("INSERT INTO location_assets(slug,name_en,category,model_path,revision,created_at,updated_at,appearance_mode,visual_material) VALUES(?,?,?,?,?,?,?,?,?)",
                           ('old_asset','Old','prop','',1,1,1,'atlas','SmoothPlastic'))
            self.assertEqual(store.get('old_asset')['appearanceMode'],'atlas')
            self.assertEqual(store.get('old_asset')['visualMaterial'],'SmoothPlastic')

    def test_implicit_atlas_source_uses_combined_mode_for_existing_api_callers(self):
        with TemporaryDirectory() as folder:
            root=Path(folder);fbx=root/'model.fbx';fbx.write_bytes(b'fixture')
            image=root/'torch_4x4_atlas.png';Image.new('RGB',(4,4),'white').save(image)
            store=LocationAssetStore(root)
            with patch('location_asset_store.inspect_location_fbx',return_value=ANALYSIS):
                created=store.register({'slug':'torch','nameEn':'Torch','category':'prop',
                                        'modelSourcePath':str(fbx),'inspectFbx':True,
                                        'textureSourcePath':str(image)})
            self.assertEqual(created['appearanceMode'],'material_atlas')
            self.assertEqual(created['visualMaterial'],'Plastic')
            self.assertGreater(created['atlasVariantId'],0)

    def test_binding_changes_mode_without_republishing_or_mutating_other_consumer(self):
        with TemporaryDirectory() as folder:
            root=Path(folder);source=root/'test.fbx';source.write_bytes(b'FBX fixture')
            image=root/'lamp_4x4_atlas.png';Image.new('RGB',(4,4),'white').save(image)
            store=LocationAssetStore(root)
            variant=store.atlases.adopt_file(str(image))
            with patch('location_asset_store.inspect_location_fbx',return_value=ANALYSIS):
                row=store.register({'nameEn':'Lantern','slug':'lantern','category':'prop',
                                    'modelSourcePath':str(source),'inspectFbx':True,
                                    'appearanceMode':'material','visualMaterial':'Plastic',
                                    'meshOptions':{'glass':{'appearanceMode':'material_atlas',
                                                            'visualMaterial':'Glass','visualColor':'#E0E0E0',
                                                            'atlasVariantId':variant['id']}}})
            self.assertEqual(row['appearanceMode'],'material')
            self.assertEqual(row['meshOptions']['glass']['atlasVariantId'],variant['id'])
            self.assertNotIn('rig_carrier',row['meshOptions'])
            with store.atlases.connect() as db:
                db.execute('UPDATE texture_atlas_variants SET published_id=?,published_sha256=source_sha256 WHERE id=?',
                           ('987654321',variant['id']))
            store.atlases.bind('location_asset','other',variant['id'])
            other=store.atlases.binding('location_asset','other')
            edited=store.select_atlas('lantern',variant['id'],row['revision'])
            self.assertEqual(edited['appearanceMode'],'material_atlas')
            self.assertEqual(edited['visualMaterial'],'Plastic')
            self.assertEqual(edited['atlasVariantId'],variant['id'])
            self.assertEqual(store.atlases.binding('location_asset','other'),other)
            # Standalone material edits never alter the variant or MeshPart override.
            saved=store.register({'slug':'lantern','nameEn':'Lantern','category':'prop',
                                  'appearanceMode':'material_atlas','visualMaterial':'Concrete',
                                  'visualColor':'#AABBCC','alphaEnabled':False})
            self.assertEqual(saved['atlasVariantId'],variant['id'])
            self.assertEqual(saved['meshOptions']['glass']['atlasVariantId'],variant['id'])
            self.assertEqual(saved['visualColor'],'#AABBCC')
            self.assertEqual(store.atlases.binding('location_asset','other'),other)
