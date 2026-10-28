"""Regress Real Estate sync, WebP staging and independent authoring controls."""
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from real_estate.studio_sync import RealEstateStudioSync
from real_estate.publication_textures import prepare_texture, published_format
from api import real_estate


class RealEstatePublicationTests(unittest.TestCase):
    def test_webp_is_converted_to_png_in_temporary_path(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'house.webp'
            Image.new('RGBA', (3, 2), (20, 30, 40, 0)).save(source, 'WEBP', lossless=True)
            original = source.read_bytes()
            result = prepare_texture(root, 'house', source, root / 'tmp')
            self.assertEqual(result, root / 'tmp/house.png')
            with Image.open(result) as converted:
                self.assertEqual(converted.format, 'PNG')
                self.assertEqual(converted.size, (3, 2))
                self.assertEqual(converted.mode, 'RGBA')
                self.assertEqual(converted.getpixel((0, 0))[3], 0)
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(published_format(source), 'png')
            self.assertEqual(published_format(root / 'door.jpeg'), 'source')

    def test_jpg_png_jpeg_sources_pass_through(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for extension in ('.png', '.jpg', '.jpeg'):
                source = root / ('door' + extension)
                source.write_bytes(b'original')
                self.assertEqual(prepare_texture(root, 'door', source, root / 'tmp'), source)
                self.assertEqual(source.read_bytes(), b'original')
            self.assertFalse((root / 'tmp').exists())

    def test_corrupt_webp_reports_clean_error_and_keeps_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'house.webp'
            source.write_bytes(b'not a webp')
            with self.assertRaisesRegex(ValueError, 'WebP conversion failed for house'):
                prepare_texture(root, 'house', source, root / 'tmp')
            self.assertEqual(source.read_bytes(), b'not a webp')
            self.assertEqual(list((root / 'tmp').iterdir()), [])

    def test_blender_is_not_used_to_convert_images(self):
        conversion = (ROOT / 'system/control-center/real_estate/publication_textures.py').read_text('utf-8')
        self.assertNotIn('blender_executable', conversion)
        self.assertNotIn('subprocess', conversion)
        self.assertFalse((ROOT / 'system/asset-manager/convert_publication_texture.py').exists())
        self.assertIn('Pillow', (ROOT / 'system/control-center/requirements-host.txt').read_text('utf-8'))

    def test_sync_rejects_unpublished(self):
        row={'status':'UPDATE_AVAILABLE','slug':'house_level1_01'}
        service=RealEstateStudioSync(SimpleNamespace(get=lambda _:row),lambda *a,**kw:self.fail('called bridge'))
        with self.assertRaisesRegex(ValueError,'publish'):
            service.sync(row['slug'])

    def test_sync_routes_and_studio_validation(self):
        row={
            'status':'PUBLISHED','slug':'house_level1_01','model_asset_id':'12345',
            'rigAssets':{'house':{'assetId':'12345'},'door':{'assetId':'12346'}},
            'house_level':1,'purchase_price':2,'min_level':3,'sale_price':4,
            'skeleton':{'meshes':[
                {'name':'house','bones':[{'name':'item_01_bone'},{'name':'chimney_bone'}]},
                {'name':'door','bones':[{'name':'door_bone'}]},
            ]},'textures':{
                'house':{'assetId':'10'},'door':{'assetId':'11'},
            },
        }
        calls=[]
        def fake_load(*args,**kwargs):
            calls.append((args,kwargs))
            return {'realEstateStats':{'bonesValidated':True,'rigsValidated':2,'texturesApplied':2},
                    'destination':'ServerStorage.real_estate.house_level1_01.model.house_level1_01'}
        service=RealEstateStudioSync(SimpleNamespace(get=lambda slug:row),fake_load)
        out=service.sync(row['slug'])
        self.assertIn('ServerStorage',out['studio']['destination'])
        args,kw=calls[0]
        self.assertEqual(args,('12345',['real_estate','house_level1_01','model']))
        self.assertEqual(kw['placement_mode'],'real-estate-rig')
        self.assertEqual(kw['metadata']['expectedMeshes']['door'],['door_bone'])
        self.assertEqual(kw['metadata']['doorModelAssetId'],'12346')
        self.assertEqual(kw['metadata']['purchasePrice'],2)
        status,result=real_estate.write('/api/real-estate/house_level1_01/sync',
            lambda:{},{'real_estate':object(),'sync_real_estate_to_studio':service.sync})
        self.assertEqual(status,200)
        self.assertEqual(result['studio'],out['studio'])

    def test_studio_model_is_structurally_separate(self):
        plugin=ROOT/'system/studio-plugin'
        model=(plugin/'modules/StudioRealEstateModel.luau').read_text('utf-8')
        bridge=(plugin/'modules/StudioModelLoadCommands.luau').read_text('utf-8')
        self.assertIn('Game1RealEstateTemplate',model)
        self.assertIn('refusing to overwrite unmanaged',model)
        self.assertIn('bonesValidated = true',model)
        self.assertIn('real-estate-rig',bridge)
        self.assertIn('StudioRealEstateModel.Place',bridge)
        self.assertIn('StudioRealEstateModel', (plugin/'plugin.project.json').read_text('utf-8'))

    def test_library_has_independent_replacement_controls(self):
        static=ROOT/'system/control-center/static'
        html=(static/'index.html').read_text('utf-8')
        js=(static/'real-estate.js').read_text('utf-8')
        for id in ('real-estate-library-rows','real-estate-sync','real-estate-library-refresh'):
            self.assertIn(f'id="{id}"',html)
        for attr in ('data-re-fbx','data-re-manage','data-re-sync'):
            self.assertIn(attr,js)
        workflow=(static/'real-estate-mesh-workflow.js').read_text('utf-8')
        self.assertIn('data-mw-use-atlas',workflow)
        self.assertIn('data-mw-publish-image',workflow)
        self.assertIn('realEstateState.textures={};realEstateState.textureRefs={};realEstateState.reuseEnabled={};',js)
        self.assertIn('if(!realEstateState.selected){',js)


if __name__ == '__main__':
    unittest.main()
