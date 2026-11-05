"""M151: mesh modal binds only controls rendered for its active tab."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "system" / "control-center" / "static"


class MeshWorkflowTabBindingM151(unittest.TestCase):
    def test_model_texture_and_collider_tabs_render_without_null_picker(self):
        node=shutil.which('node')
        if not node:self.skipTest('node unavailable')
        script=r'''
const fs=require('fs');const vm=require('vm');const assert=require('assert');
const source=fs.readFileSync('real-estate-mesh-workflow.js','utf8');
const elements=new Map();let dialog=null;
function fakeDialog(){return {
  id:'real-estate-mesh-dialog',open:false,innerHTML:'',setAttribute(){},addEventListener(){},
  showModal(){this.open=true},close(){this.open=false},
  querySelector(sel){
    if(sel==='[data-mw-close]')return {onclick:null};
    if(sel==='[data-mw-sync]')return this.innerHTML.includes('data-mw-sync')?{onclick:null}:null;
    return this.innerHTML.includes(sel.slice(1,-1))?{onclick:null}:null;
  },
  querySelectorAll(sel){return sel==='[data-mw-tab]'?[...this.innerHTML.matchAll(/data-mw-tab="([^"]+)"/g)]
      .map(m=>({dataset:{mwTab:m[1]},onclick:null})):[];}
};}
const row={slug:'house_level4_01',meshParts:['house','door','col_mesh'],
  rigAssets:{house:{assetId:'100',publishedSha256:'ok'}},
  rigSourceHashes:{house:'ok'},textures:{house:{atlasVariantId:23,atlasBindingRevision:1}},
  publicationCurrent:{}};
const ctx=vm.createContext({
 window:{game1ConsumerAtlasEditor:{newState:()=>({}),render:()=>'<div data-shared-atlas></div>',wire:()=>{}}},
 document:{getElementById:id=>elements.get(id)||null,createElement:()=>{dialog=fakeDialog();return dialog;},
 body:{appendChild:el=>elements.set(el.id,el)}},
 realEstateRows:()=>[row],realEstateIsCollider:p=>p==='col_mesh',realEstateForm:()=>{},
 realEstatePublicationBusy:()=>false,realEstateLoad:()=>{},realEstateState:{data:{publication:{configured:true},atlasCatalog:[]},atlasBusy:false},
 esc:v=>String(v??'')
});
vm.runInContext(fs.readFileSync('asset-workflow-dialog.js','utf8'),ctx);
vm.runInContext(source,ctx);
const check=code=>vm.runInContext(code,ctx);
check("realEstateMeshWorkflowOpen('house_level4_01','house')");
assert.ok(dialog.open);
assert.match(dialog.innerHTML,/data-mw-sync/);
assert.doesNotMatch(dialog.innerHTML,/data-shared-atlas/);
check("realEstateMeshWorkflow.tab='texture';realEstateMeshWorkflowRender()");
assert.match(dialog.innerHTML,/data-shared-atlas/);
assert.match(dialog.innerHTML,/data-mw-sync/);
check("realEstateMeshWorkflowOpen('house_level4_01','col_mesh')");
assert.equal(check('realEstateMeshWorkflow.tab'),'model');
assert.equal(dialog.querySelectorAll('[data-mw-tab]').length,1);
'''
        result=subprocess.run([node,'-e',script],cwd=STATIC,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)


if __name__ == "__main__":
    unittest.main()
