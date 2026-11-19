"""M371-372a: explicit per-mesh Alpha, never inferred from PNG bytes."""
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'system/control-center'))
from services.texture_alpha import texture_binding
from real_estate.store import mesh_options

class SharedMeshAlphaPolicy(unittest.TestCase):
    def test_png_alpha_is_informational_not_authorization(self):
        with TemporaryDirectory() as folder:
            root=Path(folder)
            Image.new('RGBA',(2,2),(20,30,40,0)).save(root/'translucent.png')
            default=texture_binding('body','123',root,'translucent.png')
            self.assertTrue(default['usesAlpha'])
            self.assertFalse(default['alphaEnabled'])
            enabled=texture_binding('body','123',root,'translucent.png',alpha_enabled=True)
            self.assertTrue(enabled['alphaEnabled'])
            self.assertRaises(ValueError, texture_binding, 'body','123',root,'translucent.png',alpha_enabled=1)

    def test_two_parts_with_same_atlas_have_independent_alpha(self):
        options=mesh_options(('plants','windows','stone'),{
            'plants':{'appearanceMode':'atlas','alphaEnabled':True},
            'windows':{'appearanceMode':'atlas','alphaEnabled':False},
            'stone':{'appearanceMode':'material','visualMaterial':'Slate'},
        })
        self.assertTrue(options['plants']['alphaEnabled'])
        self.assertFalse(options['windows']['alphaEnabled'])
        self.assertFalse(options['stone']['alphaEnabled'])

    def test_actors_transport_explicit_alpha_only(self):
        from services.studio_asset_sync import StudioAssetSyncService
        with TemporaryDirectory() as folder:
            root=Path(folder)
            Image.new('RGBA',(1,1),(1,2,3,0)).save(root/'alpha.png')
            row={'slug':'npc_one','model_asset_id':'55','storage_type':'swords',
                 'skeleton_json':'{"bones":[]}',
                 'textures':[{'slot':'body','asset_id':'24','source_path':'alpha.png'}],
                 'meshAppearance':{'helmet':{'alphaEnabled':True}}}
            class Store:
                def __init__(self): self.root=root
                def get(self,slug): return row
            sent=[]
            def loader(*args,**kwargs):
                sent.append(kwargs['metadata'])
                return {'monsterStats':{'textures':{'applied':1}},
                        'rigStats':{'baseParts':1,'bones':1,'boneNames':['root']}}
            store=Store()
            service=StudioAssetSyncService(None,store,store,store,loader)
            for kind in ('weapon','monster','npc'):
                if kind=='weapon': service.sync_weapon_to_studio('npc_one')
                else: service.sync_monster_to_studio('npc_one',kind=kind)
                self.assertTrue(sent[-1]['textures'][0]['usesAlpha'])
                self.assertFalse(sent[-1]['textures'][0]['alphaEnabled'])
                self.assertTrue(sent[-1]['meshAppearance']['helmet']['alphaEnabled'])

    def test_central_consumer_only_reads_explicit_flag(self):
        common=(ROOT/'system/studio-plugin/modules/StudioTextureAppearance.luau').read_text(encoding='utf8')
        house=(ROOT/'system/studio-plugin/modules/StudioRealEstateAppearance.luau').read_text(encoding='utf8')
        location=(ROOT/'system/studio-plugin/modules/StudioLocationVisualAppearance.luau').read_text(encoding='utf8')
        models=(ROOT/'system/studio-plugin/modules/StudioModelLoadCommands.luau').read_text(encoding='utf8')
        self.assertIn('function StudioTextureAppearance.ApplyVisual(',common)
        self.assertIn('opts.alphaEnabled==true',common)
        self.assertIn('Texture.ApplyVisual(mesh,settings',house)
        self.assertNotIn('and alpha==true',house)
        self.assertIn('Texture.ApplyVisual(mesh,row',location)
        self.assertIn('texture.alphaEnabled',models)
        self.assertIn('explicitMeshAlpha(mesh,',models)
        self.assertNotIn('texture.usesAlpha)',models)

if __name__=='__main__': unittest.main()
