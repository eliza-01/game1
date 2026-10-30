"""M145: Real Estate must render collision policies, and notifications never expire."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / 'system/control-center/static'


class RealEstateUiM145(unittest.TestCase):
    def node(self, code):
        binary = shutil.which('node')
        if not binary:
            self.skipTest('Node.js runtime unavailable')
        result = subprocess.run([binary, '-e', code], cwd=STATIC, text=True,
                                encoding='utf-8', capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_library_renders_each_house_collider_without_tdz_error(self):
        self.node(r'''
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const elements = new Map();
const $ = id => {
  if(!elements.has(id))elements.set(id, {
    innerHTML:'', textContent:'', hidden:true,
    querySelectorAll(){return []}, addEventListener(){}
  });
  return elements.get(id);
};
const context = vm.createContext({$, esc: value => String(value??''),
  window:{}, localStorage:{setItem(){},getItem(){return null}},
  toast(){}, request(){}});
vm.runInContext(fs.readFileSync('real-estate.js','utf8'),context);
context.realEstateRenderAtlasLibrary = () => {};
context.realEstateIdentity = () => {};
vm.runInContext(`
  realEstateState.selected = 'house_level4_01';
  realEstateState.data = {publication:{configured:true},items:[
    {slug:'house_level4_01',status:'PUBLISHED',meshParts:['col_mesh'],
     meshOptions:{col_mesh:{destructible:true}},rigAssets:{},textures:{},
     publicationCurrent:{},rigSourceHashes:{}},
    {slug:'house_level3_01',status:'PUBLISHED',meshParts:['col_mesh'],
     meshOptions:{col_mesh:{destructible:false}},rigAssets:{},textures:{},
     publicationCurrent:{},rigSourceHashes:{}}
  ]};
  realEstateRender();`,context);
const html = $('real-estate-library-rows').innerHTML;
assert.match(html,/Destructible · no bounce/);
assert.match(html,/Solid · bounce/);
assert.match(html,/house_level4_01/);
assert.match(html,/house_level3_01/);
''')

    def test_global_toast_close_replacement_and_no_expiry(self):
        self.node(r'''
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const full = fs.readFileSync('character-assets.js','utf8');
const source = full.slice(full.indexOf('function toast('), full.indexOf('async function request('));
assert.ok(source.includes('function toast('));
const toastNode = {className:'', children:[],
  replaceChildren(){this.children=[]},
  append(...children){this.children.push(...children)},
  setAttribute(name,value){this[name]=value}};
const context = vm.createContext({$:(id)=>id==='toast'?toastNode:null,
  document:{createElement(tag){return {tag,setAttribute(name,value){this[name]=value}}}},
  setTimeout(){throw Error('toast must not start an expiry timer')},
  clearTimeout(){throw Error('toast must not schedule or clear expiry timers')}});
vm.runInContext(source,context);
vm.runInContext("toast('first error',true)",context);
assert.equal(toastNode.className,'toast show error');
assert.equal(toastNode.children.length,2);
assert.equal(toastNode.children[0].textContent,'first error');
const oldClose = toastNode.children[1];
vm.runInContext("toast('new result')",context);
assert.equal(toastNode.className,'toast show');
assert.equal(toastNode.children[0].textContent,'new result');
assert.notEqual(toastNode.children[1],oldClose);
toastNode.children[1].onclick();
assert.equal(toastNode.className,'toast');
''')

    def test_locations_use_same_toast_and_cache_revisions_are_bumped(self):
        locations = (STATIC / 'locations.js').read_text(encoding='utf-8')
        html = (STATIC / 'index.html').read_text(encoding='utf-8')
        self.assertNotIn('function toast(', locations)
        self.assertIn('character-assets.js?v=19', html)
        self.assertIn('real-estate.js?v=19', html)
        self.assertIn('locations.js?v=2', html)


if __name__ == '__main__':
    unittest.main()
