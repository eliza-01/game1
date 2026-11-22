"""M437: source-of-truth checks for create-only visual authoring defaults."""
from __future__ import annotations
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'system/control-center'))
from services.mesh_authoring_policy import (new_location_mesh_options,normalize_location_options)
from real_estate.store import mesh_options

class NewAssetDefaultsM437(unittest.TestCase):
    def setUp(self):
        self.analysis={'meshes':[{'name':'rig_carrier'},{'name':'Stone'},{'name':'glass_window'},
                                 {'name':'COL_legacy'}]}
    def test_new_asset_mesh_defaults_are_material_atlas_and_no_collide(self):
        seeded=new_location_mesh_options(self.analysis,None)
        normalized=normalize_location_options(self.analysis,seeded)
        self.assertEqual(set(normalized),{'Stone','glass_window'})
        for settings in normalized.values():
            self.assertTrue(settings['noCollide'])
            self.assertEqual(settings['appearanceMode'],'material_atlas')
            self.assertEqual(settings['visualMaterial'],'Plastic')
            self.assertEqual(settings['visualColor'],'#FFFFFF')
    def test_existing_meshes_are_not_reinterpreted(self):
        previous=normalize_location_options(self.analysis,{})
        self.assertFalse(previous['Stone']['noCollide'])
        self.assertNotIn('appearanceMode',previous['Stone'])
        self.assertEqual(normalize_location_options(self.analysis,previous),previous)
    def test_explicit_overrides_stay_authoritative(self):
        seeded=new_location_mesh_options(self.analysis,{'Stone':{'noCollide':False,'appearanceMode':'material'}})
        normalized=normalize_location_options(self.analysis,seeded)
        self.assertFalse(normalized['Stone']['noCollide'])
        self.assertEqual(normalized['Stone']['appearanceMode'],'material')
        with self.assertRaisesRegex(ValueError,'missing FBX meshes'):
            normalize_location_options(self.analysis,new_location_mesh_options(self.analysis,{'missing':{}}))
    def test_house_stays_material_and_non_colliding(self):
        house=mesh_options(('walls_outside','roof'),None)
        self.assertTrue(all(x['noCollide'] and x['appearanceMode']=='material' for x in house.values()))
    def test_new_registration_persists_appearance_and_requires_real_variant(self):
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from PIL import Image
        from location_asset_store import LocationAssetStore
        with TemporaryDirectory() as temporary:
            root=Path(temporary)
            fbx=root/'small.fbx';fbx.write_bytes(b'fixture')
            img=root/'foliage_4x4_atlas.png';Image.new('RGB',(4,4),'white').save(img)
            store=LocationAssetStore(root)
            variant=store.atlases.adopt_file(str(img))
            data={'meshes':[{'name':'foliage','vertices':12,'bones':[]},
                            {'name':'rig_carrier','vertices':0,'bones':[]}]}
            payload={'nameEn':'Small Tree','category':'tree','slug':'small_tree',
                     'modelSourcePath':str(fbx),'inspectFbx':True,'createOnly':True,
                     'appearanceMode':'material','seedNewMeshDefaults':True,
                     'meshOptions':{'foliage':{'atlasVariantId':int(variant['id'])}}}
            with patch('location_asset_store.inspect_location_fbx',return_value=data):
                row=store.register(payload)
                self.assertEqual(row['appearanceMode'],'material')
                self.assertEqual(row['meshOptions']['foliage']['appearanceMode'],'material_atlas')
                self.assertTrue(row['meshOptions']['foliage']['noCollide'])
                self.assertEqual(row['meshOptions']['foliage']['atlasVariantId'],variant['id'])
                with self.assertRaisesRegex(ValueError,'select an Atlas Registry variant'):
                    store.register({**payload,'slug':'unbound','nameEn':'Unbound','meshOptions':{}})
                self.assertIsNone(store.get('unbound'))

if __name__=='__main__': unittest.main()
