"""M107 Real Estate behavior contracts: multi-rig metadata, storage, transport and upload staging."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))

from real_estate.contracts import identity, parse_name, prices, validate_analysis, assert_skeleton_survived
from real_estate.store import RealEstateStore
from real_estate.textures import TEXTURE_EXTENSIONS, available_textures
from api import write_files
from api import real_estate


def skeleton():
    return {'schemaVersion': 1, 'meshes': [
        {'name': 'house', 'armature': 'house_armature', 'vertices': 18,
         'bones': [
             {'name': 'item_01_bone', 'parent': '', 'matrixLocal': [1.0] * 16},
             {'name': 'chimney_bone', 'parent': 'item_01_bone', 'matrixLocal': [2.0] * 16},
         ], 'influencedBones': ['item_01_bone', 'chimney_bone']},
        {'name': 'door', 'armature': 'door_armature', 'vertices': 12,
         'bones': [{'name': 'door_bone', 'parent': '', 'matrixLocal': [3.0] * 16}],
         'influencedBones': ['door_bone']},
    ]}


class RealEstateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        folder = self.root / 'incoming'
        folder.mkdir()
        self.fbx = folder / 'house_level1_01.fbx'
        self.fbx.write_bytes(b'FBX-for-real-estate-unit-testing')
        (folder / 'house.webp').write_bytes(b'RIFFxxxxWEBP')
        (folder / 'door.webp').write_bytes(b'RIFFyyyyWEBP')
        (folder / 'wrong.png').write_bytes(b'png')
        self.store = RealEstateStore(self.root)
        self.payload = {'houseType': 'house', 'level': 1, 'variant': '01',
                        'purchasePrice': 1, 'salePrice': 1, 'minLevel': 1,
                        'sourcePath': str(self.fbx),
                        'textures': {'house': str(folder / 'house.webp'), 'door': str(folder / 'door.webp')}}

    def tearDown(self):
        self.temp.cleanup()

    def test_name_defaults_and_editable_prices(self):
        self.assertEqual(parse_name('house_level1_01.fbx'), {'houseType':'house', 'level':1, 'variant':'01'})
        self.assertEqual(identity({'houseType':'house','level':2,'variant':'3'})['slug'], 'house_level2_03')
        self.assertEqual(prices({}), {'purchasePrice':1, 'minLevel':1, 'salePrice':1})
        for invalid in ('0', '-1', '1.5', 'nan', '3e9'):
            with self.subTest(value=invalid):
                with self.assertRaises(ValueError):prices({'purchasePrice':invalid})

    def test_two_rigs_are_required_even_without_skin_weights(self):
        valid=skeleton()
        validate_analysis(valid)
        source=json.loads(json.dumps(valid))
        source['meshes'][0]['influencedBones']=[]
        validate_analysis(source)  # unweighted source FBX is valid
        invalid=json.loads(json.dumps(valid));invalid['meshes'][1]['armature']='house_armature'
        validate_analysis(invalid)  # a shared authored rig becomes a separate copy per published mesh
        empty=json.loads(json.dumps(valid));empty['meshes'][1]['bones']=[]
        validate_analysis(empty)  # interaction bones are optional

    def test_skeleton_survival_detects_missing_bones_parent_or_pose(self):
        source=skeleton()
        assert_skeleton_survived(source, skeleton())
        for path, value in [
            ((0,'name'),'renamed_item'), ((0,'parent'),'newparent'), ((0,'matrixLocal'),[9.0]*16)]:
            changed=skeleton();changed['meshes'][0]['bones'][0][path[1]]=value
            with self.subTest(path=path),self.assertRaises(ValueError):
                assert_skeleton_survived(source,changed)
        missing=skeleton();missing['meshes'][0]['influencedBones'].remove('chimney_bone')
        with self.assertRaisesRegex(ValueError, 'chimney_bone'):
            assert_skeleton_survived(source, missing)

    def test_inspect_auto_detects_two_meshes_and_all_image_formats(self):
        folder=self.fbx.parent
        (folder/'house.jpg').write_bytes(b'JPEG')
        (folder/'door.JPEG').write_bytes(b'JPEG')
        (folder/'house.PNG').write_bytes(b'PNG')
        (folder/'unsupported.gif').write_bytes(b'GIF')
        with patch('real_estate.store.inspect', return_value=skeleton()):
            outcome=self.store.inspect(str(self.fbx))
        self.assertEqual(outcome['level'],1)
        self.assertEqual([t['name'] for t in outcome['textures']],
                         ['door.JPEG','door.webp','house.jpg','house.PNG','house.webp','wrong.png'])
        self.assertTrue(all(Path(t['path']).is_absolute() for t in outcome['textures']))
        self.assertEqual(len(outcome['analysis']['meshes']),2)
        self.assertEqual(TEXTURE_EXTENSIONS,{'.webp','.jpg','.jpeg','.png'})

    def test_registration_preserves_canonical_sources_and_metadata(self):
        with patch('real_estate.store.inspect', return_value=skeleton()):
            row=self.store.register(self.payload)
        self.assertEqual(row['status'],'LOCAL_ONLY')
        self.assertEqual(row['purchase_price'],1)
        self.assertEqual(row['sale_price'],1)
        self.assertEqual(row['min_level'],1)
        self.assertTrue((self.root/row['model_path']).is_file())
        self.assertEqual((self.root/row['model_path']).read_bytes(),self.fbx.read_bytes())
        self.assertEqual(row['skeleton']['meshes'][0]['bones'][1]['name'],'chimney_bone')
        for part in ('house','door'):
            self.assertEqual((self.root/row['textures'][part]['path']).suffix,'.webp')
        manifest=json.loads((self.root/'assets/manifests/real-estate.json').read_text('utf-8'))
        self.assertEqual(manifest['schemaVersion'],2)
        self.assertEqual(len(manifest['items']),1)

    def test_registration_accepts_explorer_selection_outside_fbx_folder(self):
        other=self.root/'other textures'
        other.mkdir()
        house=other/'stone.PNG';house.write_bytes(b'new-house-png')
        door=other/'oak.JPEG';door.write_bytes(b'new-door-jpeg')
        payload={**self.payload,'textures':{'house':str(house),'door':str(door)}}
        with patch('real_estate.store.inspect', return_value=skeleton()):
            row=self.store.register(payload)
        self.assertEqual(Path(row['textures']['house']['path']).suffix,'.png')
        self.assertEqual(Path(row['textures']['door']['path']).suffix,'.jpeg')
        self.assertEqual((self.root/row['textures']['house']['path']).read_bytes(),b'new-house-png')
        self.assertEqual((self.root/row['textures']['door']['path']).read_bytes(),b'new-door-jpeg')
        self.assertEqual(self.store.snapshot()['summary']['registered'],1)

    def test_all_supported_extensions_survive_canonical_registration(self):
        for ext in ('.webp','.png','.jpg','.jpeg'):
            with self.subTest(ext=ext):
                src=self.fbx.parent/f'house{ext}'
                src.write_bytes(('data'+ext).encode())
                payload={**self.payload,'textures':{**self.payload['textures'],'house':str(src)}}
                with patch('real_estate.store.inspect', return_value=skeleton()):
                    row=self.store.register(payload) if ext=='.webp' else self.store.register({**payload,'existingSlug':'house_level1_01','sourcePath':''})
                self.assertEqual(Path(row['textures']['house']['path']).suffix,ext)
                self.assertEqual((self.root/row['textures']['house']['path']).read_bytes(),src.read_bytes())
        self.assertEqual(self.store.snapshot()['summary']['registered'],1)

    def test_existing_house_can_replace_one_texture_via_explorer(self):
        with patch('real_estate.store.inspect', return_value=skeleton()):
            first=self.store.register(self.payload)
        elsewhere=self.root/'outside.jpg';elsewhere.write_bytes(b'outside-jpg')
        old_model=first['model_sha256']
        edit={**self.payload,'existingSlug':first['slug'],'sourcePath':'',
              'textures':{'house':str(elsewhere),'door':first['textures']['door']['path']}}
        row=self.store.register(edit)
        self.assertEqual(row['model_sha256'],old_model)
        self.assertEqual(row['textures']['door']['sha256'],first['textures']['door']['sha256'])
        self.assertEqual((self.root/row['textures']['house']['path']).read_bytes(),b'outside-jpg')
        self.assertTrue(row['textures']['house']['path'].endswith('house.jpg'))

    def test_reject_missing_and_unsupported_texture_files(self):
        other=self.root/'texture.gif';other.write_bytes(b'GIF')
        with patch('real_estate.store.inspect', return_value=skeleton()):
            for invalid in (str(other),str(self.root/'missing.png'),'',str(self.root)):
                payload={**self.payload,'textures':{**self.payload['textures'],'door':invalid}}
                with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                    self.store.register(payload)
        self.assertEqual(self.store.snapshot()['summary']['registered'],0)

    def test_native_texture_picker_route_and_cancel(self):
        from collections import defaultdict
        calls=[]
        deps=defaultdict(lambda:lambda *args,**kwargs:'')
        deps['choose_real_estate_texture']=lambda initial:(calls.append(initial) or r'C:\art\door.jpeg')
        status,result=write_files.route('/api/files/choose-real-estate-texture',
                            lambda:{'initialPath':r'C:\art\house.fbx'},deps)
        self.assertEqual((status,result),(200,{'path':r'C:\art\door.jpeg'}))
        self.assertEqual(calls,[r'C:\art\house.fbx'])
        deps['choose_real_estate_texture']=lambda initial:''
        self.assertEqual(write_files.route('/api/files/choose-real-estate-texture',lambda:{},deps),
                         (200,{'path':''}))

    def test_image_publication_mime_types_are_already_supported(self):
        from opencloud_assets import _validate_image_upload
        for ext, mime in (('.webp','image/webp'),('.png','image/png'),
                          ('.jpg','image/jpeg'),('.jpeg','image/jpeg')):
            path=self.root/('test'+ext);path.write_bytes(b'example')
            self.assertEqual(_validate_image_upload(path,'fake-credential'),mime)

    def test_ui_wires_each_mesh_to_native_picker(self):
        static=ROOT/'system/control-center/static'
        content=(static/'real-estate.js').read_text('utf-8')
        self.assertIn('function realEstateParts()',content)
        self.assertIn('realEstateBrowseTexture(part)',content)
        self.assertIn('choose-real-estate-texture',content)
        self.assertIn('textureReferences:Object.fromEntries(parts.map(',content)
        self.assertIn('real-estate.js?v=10',(static/'index.html').read_text('utf-8'))

    def test_edit_prices_without_upload_reanalysis(self):
        with patch('real_estate.store.inspect', return_value=skeleton()):
            first=self.store.register(self.payload)
        edit={**self.payload,'existingSlug':first['slug'],'sourcePath':'',
              'textures':{part:record['path'] for part,record in first['textures'].items()},
              'purchasePrice':123,'minLevel':8,'salePrice':66}
        row=self.store.register(edit)
        self.assertEqual(row['revision'],2)
        self.assertEqual((row['purchase_price'],row['min_level'],row['sale_price']),(123,8,66))
        self.assertEqual(row['model_sha256'],first['model_sha256'])
        self.assertEqual(row['skeleton'],first['skeleton'])

    def test_publish_rechecks_rigs_before_network_and_saves_assets(self):
        with patch('real_estate.store.inspect', return_value=skeleton()):
            row=self.store.register(self.payload)
        credentials={'apiKey':'test','creatorType':'user','creatorId':'123','description':'Game1 Real Estate House'}
        calls=[]
        def fake_prepare(root, src, target, expected, tex):
            self.assertEqual({*tex}, {'house','door'})
            self.assertEqual(len(expected['meshes']),2)
            target.mkdir(parents=True,exist_ok=True)
            for part in ('house','door'):
                (target/(part+'.fbx')).write_bytes(b'prepared independent rig')
            calls.append('prepared')
        def fake_create(path, **kwargs):
            calls.append(path.suffix)
            return f'operations/{len(calls)}'
        def fake_wait(op, **kwargs):
            return SimpleNamespace(asset_id=str(100+len(calls)),operation_path=op,moderation_state='Approved')
        def fake_prepare_texture(root, part, source, staging):
            output=staging/(part+'.png')
            output.write_bytes(b'valid-converted-test-png')
            return output
        with patch('real_estate.store.prepare_texture',side_effect=fake_prepare_texture),\
             patch('real_estate.store.prepare_publication',side_effect=fake_prepare),\
             patch('real_estate.store.create_model_asset',side_effect=fake_create),\
             patch('real_estate.store.create_image_asset',side_effect=fake_create),\
             patch('real_estate.store.wait_for_operation',side_effect=fake_wait):
            result=self.store.publish(row['slug'],credentials)
            self.assertEqual(result['status'],'PUBLISHED')
            self.assertEqual(len(self.store.publications(row['slug'])),4)
            self.store.publish(row['slug'],credentials)
            self.assertEqual(len(self.store.publications(row['slug'])),4)
        self.assertEqual(calls,['prepared','.fbx','.fbx','.png','.png'])
        self.assertEqual(result['textures']['house']['publicationFormat'],'png')

    def test_routes_are_isolated_and_keep_publication_configuration(self):
        with patch('real_estate.store.inspect',return_value=skeleton()):
            sources={'real_estate':self.store,'publication_config':lambda:{'configured':False}}
            status,result=real_estate.read(urlparse('/api/real-estate'),sources)
            self.assertEqual(status,200)
            self.assertFalse(result['publication']['configured'])
            status,result=real_estate.write('/api/real-estate',lambda:self.payload,{'real_estate':self.store})
            self.assertEqual(status,200)
            self.assertEqual(result['slug'],'house_level1_01')
            self.assertIsNone(real_estate.write('/api/other',lambda:{},{'real_estate':self.store}))


if __name__ == '__main__': unittest.main()
