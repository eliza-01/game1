"""M151: mesh modal binds only controls rendered for its active tab."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "system" / "control-center" / "static"


class MeshWorkflowTabBindingM151(unittest.TestCase):
    def test_model_texture_and_collider_tabs_render_without_null_picker(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js unavailable")
        script = r'''
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('real-estate-mesh-workflow.js', 'utf8');
const nodes = new Map();
let lastDialog;
function makeDialog() {
  let html='';
  const cached=new Map();
  return {
    open:false,addEventListener(){},setAttribute(){},
    get innerHTML(){return html},
    set innerHTML(value){html=value;cached.clear()},
    showModal(){this.open=true},close(){this.open=false},
    querySelector(selector){
      if(cached.has(selector))return cached.get(selector);
      if(selector === '[data-mw-atlas]') {
        if(!this.innerHTML.includes('<select data-mw-atlas'))return null;
        const picker={value:'atlas:23',onchange:null};
        cached.set(selector,picker);return picker;
      }
      const match=selector.match(/^\[data-mw-([^\]]+)\]$/);
      if(!match)return null;
      if(!this.innerHTML.includes('data-mw-'+match[1]))return null;
      const button={onclick:null};cached.set(selector,button);return button;
    },
    querySelectorAll(selector){
      if(selector!=='[data-mw-tab]')return [];
      if(cached.has(selector))return cached.get(selector);
      const tabs=[...this.innerHTML.matchAll(/data-mw-tab="([^"]+)"/g)]
        .map(m=>({dataset:{mwTab:m[1]},onclick:null}));
      cached.set(selector,tabs);return tabs;
    }
  };
}
const row={slug:'house_level4_01',meshParts:['house','door','col_mesh'],
  rigAssets:{},rigSourceHashes:{},textures:{},publicationCurrent:{}};
const ctx=vm.createContext({
  document:{
    getElementById(id){return nodes.get(id)||null},
    createElement(tag){assert.equal(tag,'dialog');lastDialog=makeDialog();return lastDialog},
    body:{appendChild(el){nodes.set(el.id,el)}}
  },
  realEstateRows:()=>[row],realEstateIsCollider:p=>p==='col_mesh',
  realEstateForm(){},realEstatePublicationBusy:()=>false,
  realEstatePublishedAtlasChoices:()=>[{reference:'atlas:23',filename:'foo.png',assetId:'123'}],
  realEstateState:{data:{publication:{configured:true}},atlasBusy:false,publicationJob:null},
  esc:value=>String(value??'')
});
vm.runInContext(source,ctx);
const check=(js)=>vm.runInContext(js,ctx);
// Before M151 this opening threw at picker.onchange: picker is null on model tab.
check("realEstateMeshWorkflowOpen('house_level4_01','house')");
assert.equal(lastDialog.open,true);
assert.match(lastDialog.innerHTML,/data-mw-replace/);
assert.equal(lastDialog.querySelector('[data-mw-atlas]'),null);
check('realEstateMeshWorkflowRender()'); // Real Estate page rerender while modal is open
// Switch from Model to Texture; atlas controls must become live.
const texture=lastDialog.querySelectorAll('[data-mw-tab]').find(t=>t.dataset.mwTab==='texture');
assert.ok(texture);
texture.onclick();
assert.match(lastDialog.innerHTML,/data-mw-atlas/);
assert.equal(check('realEstateMeshWorkflow.tab'),'texture');
// A selector change rerenders the modal without throwing.
const picker=lastDialog.querySelector('[data-mw-atlas]');
assert.equal(typeof picker.onchange,'function');
picker.onchange();
assert.equal(check('realEstateMeshWorkflow.chosenAtlasId'),23);
// Switch back to model; no atlas picker exists, but modal must remain active.
lastDialog.querySelectorAll('[data-mw-tab]').find(t=>t.dataset.mwTab==='model').onclick();
assert.equal(check('realEstateMeshWorkflow.tab'),'model');
assert.equal(lastDialog.querySelector('[data-mw-atlas]'),null);
// Collider has no texture tab; model editor still opens.
check("realEstateMeshWorkflowOpen('house_level4_01','col_mesh')");
assert.equal(check('realEstateMeshWorkflow.tab'),'model');
assert.equal(lastDialog.querySelectorAll('[data-mw-tab]').length,1);
// Atlas entry points should still open directly on the texture tab.
check("realEstateMeshWorkflowOpen('house_level4_01','door','texture')");
assert.equal(check('realEstateMeshWorkflow.tab'),'texture');
assert.match(lastDialog.innerHTML,/<select data-mw-atlas/);
'''
        result = subprocess.run([node, "-e", script], cwd=STATIC,
                                text=True, encoding="utf-8", capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_new_js_version_is_used_and_is_valid(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        self.assertIn('real-estate-mesh-workflow.js?v=2', html)
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js unavailable")
        result = subprocess.run([node, "--check", str(STATIC / "real-estate-mesh-workflow.js")],
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
