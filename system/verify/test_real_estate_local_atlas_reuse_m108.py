"""M108: New Estate can reuse its own unpublished house atlas; catalog is filterable."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from real_estate.store import RealEstateStore
from test_real_estate_m107 import skeleton


class LocationCatalog:
    def list(self):
        return [
            {'slug':'granite-wall','name_en':'Granite Wall','category':'rock',
             'category_label':'Rocks','texture_path':'assets/granite.png',
             'texture_sha256':'rock-sha','texture_published_sha256':'rock-sha',
             'texture_asset_id':'88001'},
            {'slug':'oak-fence','name_en':'Oak Fence','category':'fence',
             'category_label':'Fences','texture_path':'assets/oak.png',
             'texture_sha256':'fence-sha','texture_published_sha256':'fence-sha',
             'texture_asset_id':'88002'},
            {'slug':'pending-building','name_en':'Incomplete Building',
             'category':'building','category_label':'Buildings',
             'texture_path':'assets/pending.png','texture_sha256':'new',
             'texture_published_sha256':'old','texture_asset_id':'88003'},
        ]


class LocalAtlasTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='m108-atlas-')
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        art=self.root/'art';art.mkdir()
        self.model=art/'house_level5_01.fbx';self.model.write_bytes(b'model')
        self.atlas=art/'house.webp';self.atlas.write_bytes(b'atlas-v1')
        self.store=RealEstateStore(self.root,location_assets=LocationCatalog())
        self.request={'sourcePath':str(self.model),'houseType':'house','level':5,'variant':'01',
                      'textures':{'house':str(self.atlas),'door':''},
                      'textureReferences':{'door':'mesh:house'}}
        self.events=[]
        self.counter=iter(range(10001,10040))

    def register(self, payload=None):
        with patch('real_estate.store.inspect',return_value=skeleton()):
            return self.store.register(payload or self.request)

    def publish(self, scope='all'):
        def stage(root,source,dest,expected,textures):
            self.assertEqual(set(textures),{'house','door'})
            self.assertEqual(Path(textures['house']).read_bytes(), Path(textures['door']).read_bytes())
            dest.mkdir(parents=True)
            for part in ('house','door'):(dest/f'{part}.fbx').write_bytes(part.encode())
        def model(path,**kw):
            self.events.append('model:'+path.stem)
            return 'operation:model:'+path.stem
        def image(path,**kw):
            self.events.append('image:'+kw['display_name'].split()[-1])
            return 'operation:image:'+kw['display_name'].split()[-1]
        def wait(operation,**kw):
            return SimpleNamespace(asset_id=str(next(self.counter)),
                                   moderation_state='Approved',operation_path=operation)
        with patch('real_estate.store.prepare_publication',side_effect=stage), \
             patch('real_estate.store.prepare_texture',side_effect=lambda root,part,path,stage:path), \
             patch('real_estate.store.create_model_asset',side_effect=model), \
             patch('real_estate.store.create_image_asset',side_effect=image), \
             patch('real_estate.store.wait_for_operation',side_effect=wait):
            return self.store.publish('house_level5_01',
                                      {'apiKey':'test','creatorType':'user','creatorId':'1'},scope=scope)

    def test_new_estate_local_atlas_works_before_any_image_upload(self):
        row=self.register()
        self.assertEqual(row['status'],'LOCAL_ONLY')
        self.assertEqual(row['textures']['door']['reuseReference'],'mesh:house')
        self.assertEqual(row['textures']['door']['path'],row['textures']['house']['path'])
        self.assertEqual(row['textures']['door']['sha256'],row['textures']['house']['sha256'])
        self.assertEqual(row['textures']['door']['assetId'],'')
        self.assertFalse(row['publicationCurrent']['house'])
        self.assertFalse(row['publicationCurrent']['door'])
        manifest=json.loads((self.root/'assets/manifests/real-estate.json').read_text())
        self.assertEqual(manifest['items'][0]['textures']['door']['reuseReference'],'mesh:house')
        with self.store.connect() as db:
            saved=json.loads(db.execute('SELECT textures_json FROM real_estate').fetchone()[0])
        self.assertEqual(saved['door']['reuseReference'],'mesh:house')
        self.assertEqual(saved['door']['assetId'],'')

    def test_publish_model_before_atlas_then_publish_house_only(self):
        self.register()
        result=self.publish(scope='model')
        self.assertTrue(result['publicationCurrent']['model'])
        self.assertFalse(result['publicationCurrent']['door'])
        self.assertEqual(self.events,['model:house','model:door'])
        self.events.clear()
        result=self.publish(scope='all')
        self.assertEqual(self.events,['image:house'])
        self.assertTrue(result['publicationCurrent']['house'])
        self.assertTrue(result['publicationCurrent']['door'])
        self.assertEqual(result['textures']['door']['assetId'],result['textures']['house']['assetId'])
        self.assertEqual(result['status'],'PUBLISHED')
        self.events.clear()
        self.publish(scope='door')
        self.assertEqual(self.events,[])
        self.assertNotIn('door', [r['part'] for r in self.store.publications(result['slug'])])

    def test_single_publish_all_creates_only_one_image_for_two_meshes(self):
        self.register()
        result=self.publish()
        self.assertEqual(self.events,['model:house','model:door','image:house'])
        self.assertEqual(result['textures']['door']['assetId'],result['textures']['house']['assetId'])

    def test_replacing_house_atlas_invalidates_both_images_without_duplicate_upload(self):
        self.register()
        first=self.publish()
        previous=first['textures']['house']['assetId']
        replacement=self.root/'art'/'new-house.png';replacement.write_bytes(b'atlas-v2')
        edit={**self.request,'existingSlug':first['slug'],'sourcePath':'',
              'textures':{'house':str(replacement),'door':''}}
        pending=self.store.register(edit)
        self.assertEqual(pending['textures']['door']['assetId'],previous)
        self.assertFalse(pending['publicationCurrent']['door'])
        self.events.clear()
        updated=self.publish(scope='house')
        self.assertEqual(self.events,['image:house'])
        self.assertNotEqual(updated['textures']['house']['assetId'],previous)
        self.assertEqual(updated['textures']['door']['assetId'],updated['textures']['house']['assetId'])
        self.assertTrue(updated['publicationCurrent']['door'])

    def test_door_publication_before_owning_atlas_explains_dependency(self):
        self.register()
        with self.assertRaisesRegex(ValueError,'Publish the house image first'):
            self.publish(scope='door')
        self.assertEqual(self.events,[])

    def test_invalid_local_reference_for_house_is_rejected(self):
        invalid={**self.request,'textureReferences':{'house':'mesh:house','door':''}}
        with self.assertRaisesRegex(ValueError,'cannot reuse its own'):
            self.register(invalid)

    def test_location_references_have_real_categories_and_only_published_images(self):
        choices=self.store.texture_references()
        categories={e['reference']:e.get('category') for e in choices}
        self.assertEqual(categories,{'location:granite-wall':'rock','location:oak-fence':'fence'})
        self.assertEqual(choices[0]['categoryLabel'],'Rocks')
        self.assertTrue(all(e['group']=='location' for e in choices))

    @unittest.skipUnless(shutil.which('node'), 'Node.js needed for JavaScript behavior test')
    def test_search_and_category_preserve_selected_source_and_local_atlas(self):
        script=r'''
const fs=require('fs'),vm=require('vm');
const elements={};
const context={window:{},localStorage:{getItem:()=>null,setItem:()=>{}},
  $:(key)=>elements[key]||(elements[key]={hidden:true,addEventListener:()=>{}}),
  esc:s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),
  request:()=>{},toast:()=>{},console};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),context);
const output=vm.runInContext(`(() => {
 realEstateState.data={textureReferences:[
  {group:'location',reference:'location:granite-wall',category:'rock',categoryLabel:'Rocks',label:'Granite Wall',assetId:'88001'},
  {group:'location',reference:'location:oak-fence',category:'fence',categoryLabel:'Fences',label:'Oak Fence',assetId:'88002'},
  {group:'estate',reference:'estate:other:house',label:'other / house',assetId:'88003'}
 ]};
 realEstateState.textureRefs.door='location:oak-fence';
 realEstateState.reuseFilters.door={category:'rock',query:'granite'};
 const filtered=realEstateReuseOptions('door');
 const categories=realEstateLocationCategories();
 realEstateState.reuseFilters.door={category:'',query:'oak'};
 const searched=realEstateReuseOptions('door');
 return {filtered,searched,categories};
})()`,context);
if(!output.filtered.includes('This Estate')||!output.filtered.includes('mesh:house'))process.exit(11);
if(!output.filtered.includes('Granite Wall')||!output.filtered.includes('Oak Fence'))process.exit(12);
if(!output.filtered.includes('Location Assets · Rocks'))process.exit(13);
if(output.filtered.includes('other / house'))process.exit(14);
if(!output.searched.includes('Oak Fence')||output.searched.includes('Granite Wall'))process.exit(15);
if(output.categories.length!==2)process.exit(16);
'''
        output=subprocess.run([shutil.which('node'),'-e',script,
                                str(ROOT/'system/control-center/static/real-estate.js')],
                               text=True,capture_output=True)
        self.assertEqual(output.returncode,0,output.stderr+output.stdout)


if __name__=='__main__':
    unittest.main()
