"""M141: independent authored atlas versions, shared resolution variants, correct reuse labels."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock
import shutil
import subprocess

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services.texture_atlas_registry import AtlasRegistry, parse_filename, same_atlas_series
from real_estate.store import RealEstateStore
from test_real_estate_m107 import skeleton


class VersionedAtlasContractTests(TestCase):
    def setUp(self):
        tmp=TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.input=self.root/'incoming'
        self.input.mkdir()
        (self.root/'.control-center').mkdir()
        self.atlases=AtlasRegistry(self.root)

    def image(self, filename: str, size: int, color: str):
        path=self.input/filename
        Image.new('RGBA',(size,size),color).save(path)
        return path

    def publish_locally(self, variant, image_id):
        with self.atlases.connect() as db:
            db.execute('UPDATE texture_atlas_variants SET published_id=?,published_sha256=source_sha256 WHERE id=?',
                       (image_id,variant['id']))

    def test_version_is_not_resolution_and_keeps_independent_published_id(self):
        first=self.atlases.register_file(str(self.image('restoration_01_64x64_atlas.png',64,'red')))
        second=self.atlases.register_file(str(self.image('restoration_02_64x64_atlas.png',64,'blue')))
        small=self.atlases.register_file(str(self.image('restoration_01_32x32_atlas.png',32,'green')))
        self.publish_locally(first,'91001')
        self.publish_locally(second,'91002')
        self.publish_locally(small,'91003')
        catalog=self.atlases.catalog()
        self.assertEqual([(family['atlasKey'],family['version']) for family in catalog],
                         [('restoration_01','01'),('restoration_02','02')])
        self.assertEqual([v['id'] for v in catalog[0]['variants']],[first['id'],small['id']])
        self.assertEqual(self.atlases.get_variant(first['id'])['published_id'],'91001')
        self.assertEqual(self.atlases.get_variant(second['id'])['published_id'],'91002')
        self.assertEqual(parse_filename('restoration_02_64x64_atlas.png')['baseKey'],'restoration')
        self.assertEqual(parse_filename('house_level4_01_4096x4096_atlas.png')['version'],'01')
        self.assertTrue(same_atlas_series('restoration_01','restoration_02'))
        self.assertFalse(same_atlas_series('restoration_01','door_02'))
        self.assertFalse(same_atlas_series('restoration','door'))
        self.assertIsNone(parse_filename('restoration_01_atlas.png'))

    def test_change_version_changes_only_selected_mesh_binding_no_upload(self):
        fbx=self.input/'house_level2_01.fbx'
        fbx.write_bytes(b'original model')
        first=self.atlases.register_file(str(self.image('house_level2_01_64x64_atlas.png',64,'red')))
        second=self.atlases.register_file(str(self.image('house_level2_02_64x64_atlas.png',64,'blue')))
        self.publish_locally(first,'91001')
        self.publish_locally(second,'91002')
        store=RealEstateStore(self.root)
        payload={'houseType':'house','level':2,'variant':'01','sourcePath':str(fbx),
                 'textures':{'house':'','door':''},
                 'textureReferences':{'house':f'atlas:{first["id"]}','door':'mesh:house'}}
        with mock.patch('real_estate.store.inspect',return_value=skeleton()):
            row=store.register(payload)
        with store.connect() as db:
            db.execute('UPDATE real_estate SET model_rigs_json=?, model_asset_id=?, model_published_hash=? WHERE slug=?',
                       (json.dumps({'house':{'assetId':'111','publishedSha256':row['model_sha256']},
                                    'door':{'assetId':'222','publishedSha256':row['model_sha256']}}),
                        '111',row['model_sha256'],row['slug']))
        initial=store.get(row['slug'])
        self.assertFalse(initial['textures']['house']['atlasLegacyWarning'])
        self.assertEqual([v['version'] for v in initial['textures']['house']['atlasVersionChoices']],['01','02'])
        with mock.patch('services.texture_atlas_registry.create_image_asset') as upload:
            updated=store.select_atlas(row['slug'],'house',second['id'],expected_revision=1)
            upload.assert_not_called()
        self.assertEqual(updated['textures']['house']['assetId'],'91002')
        self.assertEqual(updated['textures']['door']['assetId'],'91002')
        self.assertEqual(updated['textures']['house']['atlasVersion'],'02')
        self.assertEqual(updated['rigAssets'],initial['rigAssets'])
        self.assertEqual(self.atlases.get_variant(first['id'])['published_id'],'91001')
        self.assertEqual(self.atlases.get_variant(second['id'])['published_id'],'91002')
        with self.assertRaisesRegex(ValueError,'same mesh series'):
            unrelated=self.atlases.register_file(str(self.image('unrelated_01_64x64_atlas.png',64,'pink')))
            self.publish_locally(unrelated,'99099')
            store.select_atlas(row['slug'],'house',unrelated['id'],expected_revision=2)


    def test_legacy_estate_reuse_exposes_owner_filename_without_spurious_warning(self):
        store=RealEstateStore(self.root)
        original=self.image('old_owner.png',64,'green')
        fbx=self.input/'house_level3_01.fbx'
        fbx.write_bytes(b'owner model')
        with mock.patch('real_estate.store.inspect',return_value=skeleton()):
            first=store.register({'houseType':'house','level':3,'variant':'01',
                'sourcePath':str(fbx),'textures':{'house':str(original),'door':''},
                'textureReferences':{'door':'mesh:house'}})
        with store.connect() as db:
            raw=db.execute('SELECT textures_json FROM real_estate WHERE slug=?',
                           (first['slug'],)).fetchone()[0]
            data=json.loads(raw)
            # Pre-registry legacy publication: bytes stored under a generic path,
            # but original artwork had a standard versioned filename.
            data['house']['filename']='restoration_01_64x64_atlas.png'
            data['house']['assetId']='12345'
            data['house']['publishedSha256']=data['house']['sha256']
            from real_estate.publication_textures import published_format
            data['house']['publicationFormat']=published_format(Path(data['house']['path']))
            db.execute('UPDATE real_estate SET textures_json=? WHERE slug=?',
                       (json.dumps(data),first['slug']))
        second_fbx=self.input/'house_level3_02.fbx'
        second_fbx.write_bytes(b'consumer model')
        with mock.patch('real_estate.store.inspect',return_value=skeleton()):
            consumer=store.register({'houseType':'house','level':3,'variant':'02',
                'sourcePath':str(second_fbx), 'textures':{'house':'','door':''},
                'textureReferences':{'house':f'estate:{first["slug"]}:house',
                                     'door':'mesh:house'}})
        reused=consumer['textures']['house']
        self.assertEqual(reused['filename'],'restoration_01_64x64_atlas.png')
        self.assertFalse(reused['atlasLegacyWarning'])
        self.assertEqual(reused['atlasVersion'],'01')
        self.assertEqual(reused['assetId'],'12345')
        self.assertEqual(consumer['textures']['door']['assetId'],'12345')

    def test_effective_reused_filename_is_validated_not_blank_local_reference(self):
        store=RealEstateStore(self.root)
        # The legacy row may contain only a reference until its owner resolves.
        raw={'filename':'', 'path':'', 'reuseReference':'estate:owner:house'}
        owner={'filename':'restoration_01_64x64_atlas.png','path':'assets/restoration.png',
               'sha256':'abc','assetId':'111'}
        effective=store._atlas_presentation({**raw,**owner}, {})
        self.assertFalse(effective['atlasLegacyWarning'])
        self.assertEqual(effective['atlasKey'],'restoration_01')
        self.assertEqual(effective['atlasVersion'],'01')


class VersionPickerUITests(TestCase):
    def test_ui_renders_and_selects_published_version(self):
        if not shutil.which('node'):
            self.skipTest('node unavailable')
        script=r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const elements=Object.create(null);
const $=id=>elements[id]??(elements[id]={value:'',innerHTML:'',hidden:true,addEventListener(){}});
const ctx=vm.createContext({$,esc:v=>String(v??''),window:{},localStorage:{setItem(){},getItem(){return null;}},request(){},toast(){}});
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),ctx);
const html=vm.runInContext(`realEstateAtlasVersionSelector({atlasVariantId:11,atlasVersion:'01',atlasVersionChoices:[
{id:11,version:'01',width:64,height:64,resolution:'64x64',current:true,published_id:'111'},
{id:12,version:'02',width:64,height:64,resolution:'64x64',current:true,published_id:'222'},
{id:13,version:'02',width:32,height:32,resolution:'32x32',current:false,published_id:''}
]},'restoration')`,ctx);
assert.match(html,/data-re-atlas-version-part="restoration"/);
assert.match(html,/<option value="11" selected/);
assert.match(html,/<option value="12"/);
assert.match(html,/<option value="13"[^>]+disabled/);
'''
        result=subprocess.run(['node','-e',script,str(ROOT/'system/control-center/static/real-estate.js')],
                              capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
