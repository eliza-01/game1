"""M138: a published central atlas is visible in Reuse and edit preselects it."""
from pathlib import Path
import shutil
import subprocess
from unittest import TestCase, skipUnless

ROOT = Path(__file__).resolve().parents[2]


@skipUnless(shutil.which('node'), 'Node.js required for real Estate browser-renderer test')
class RealEstateReusePickerM138Tests(TestCase):
    def test_catalog_only_variant_and_edit_preselect_registry_reference(self):
        js = ROOT / 'system/control-center/static/real-estate.js'
        code = r'''
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const elements=Object.create(null);
const $=id=>elements[id]??(elements[id]={value:'',innerHTML:'',hidden:true,textContent:'',addEventListener(){}});
const esc=v=>String(v??'');
const ctx=vm.createContext({$,esc,window:{},localStorage:{setItem(){},getItem(){return null;}},request(){},toast(){}});
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),ctx);
vm.runInContext(`realEstateState.data={
  textureReferences:[{group:'estate',reference:'estate:other:house',label:'other',filename:'house.png',assetId:'333'}],
  atlasCatalog:[{atlasKey:'house_level4_01',variants:[
    {id:5,current:true,filename:'house_level4_01_4096x4096_atlas.png',source_path:'assets/source/texture-atlases/house_level4_01/4096x4096/house_level4_01_4096x4096_atlas.png',published_id:'92116826074029'},
    {id:6,current:false,filename:'house_level4_01_2048x2048_atlas.png',published_id:''}]}],items:[]};`,ctx);
let html=vm.runInContext('realEstateReuseOptions("door")',ctx);
assert.match(html,/<option value="atlas:5">house_level4_01 · house_level4_01_4096x4096_atlas.png · 92116826074029<\/option>/);
assert.doesNotMatch(html,/atlas:6/);
vm.runInContext('realEstateState.reuseFilters.door={category:"all",query:"92116826074029"}',ctx);
html=vm.runInContext('realEstateReuseOptions("door")',ctx);
assert.match(html,/atlas:5/);
assert.doesNotMatch(html,/estate:other:house/);
vm.runInContext(`realEstateRenderTextures=()=>{}; realEstateRenderRigs=()=>{}; realEstateRender=()=>{};
const row={slug:'house_level4_01',meshParts:['house','door'],meshOptions:{},textures:{
 house:{path:'assets/source/texture-atlases/house_level4_01/4096x4096/house_level4_01_4096x4096_atlas.png',reuseReference:'',atlasVariantId:5,atlasCurrent:true},
 door:{path:'assets/source/real-estate/house_level4_01/textures/door.png',reuseReference:'',atlasVariantId:null,atlasCurrent:null}},
 skeleton:{meshes:[]}};
realEstateForm(row);`,ctx);
assert.equal(vm.runInContext('realEstateState.reuseEnabled.house',ctx),true);
assert.equal(vm.runInContext('realEstateState.textureRefs.house',ctx),'atlas:5');
assert.equal(vm.runInContext('realEstateState.textures.house',ctx),'');
assert.equal(vm.runInContext('realEstateState.reuseEnabled.door',ctx),false);
assert.equal(vm.runInContext('realEstateState.textures.door',ctx),'assets/source/real-estate/house_level4_01/textures/door.png');
const selected=vm.runInContext('realEstateReuseOptions("house")',ctx);
assert.match(selected,/<option value="atlas:5">/);
'''
        result=subprocess.run([shutil.which('node'),'-e',code,str(js)],capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_index_script_version_bumped(self):
        html=(ROOT/'system/control-center/static/index.html').read_text(encoding='utf-8')
        self.assertIn('real-estate.js?v=14',html)
