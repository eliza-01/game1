"""M383: every Real Estate per-mesh editor is collapsed by default."""
from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "system/control-center/static"


class RealEstateTextureSpoilers(unittest.TestCase):
    def test_style_covers_closed_and_expanded_mesh_editors(self):
        css = (STATIC / "real-estate.css").read_text(encoding="utf-8")
        self.assertIn('.real-estate-texture-row[open] > .real-estate-texture-heading', css)
        self.assertIn('.real-estate-texture-body { display:flex; flex-direction:column;', css)
        self.assertIn('.real-estate-texture-heading:focus-visible', css)

    @unittest.skipUnless(shutil.which("node"), "Node is required for UI test")
    def test_closed_initially_and_preserves_expanded_rows_during_mode_change(self):
        code = r'''
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const nodes=Object.create(null);
function $(id){return nodes[id]??(nodes[id]={hidden:true,innerHTML:'',textContent:'',value:'',addEventListener:()=>{}});}
const host=$('real-estate-mesh-textures');
host.querySelectorAll=(selector)=>{
  assert.equal(selector,'.real-estate-texture-row[open]');
  return [...host.innerHTML.matchAll(/<details class="real-estate-texture-row" data-texture-part="([^"]+)" open>/g)].map(m=>({dataset:{texturePart:m[1]}}));
};
const ctx=vm.createContext({$,esc:x=>String(x??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;'),window:{},request:async()=>{},toast:()=>{},console});
for(const file of process.argv.slice(1)) vm.runInContext(fs.readFileSync(file,'utf8'),ctx);
vm.runInContext(`realEstateState.inspect={analysis:{meshes:[{name:'roof'},{name:'plants'}]},textures:[]};realEstateState.data={textureReferences:[],visualMaterials:[{id:'Wood',label:'Wood'}]};realEstateRenderTextures();`,ctx);
let html=host.innerHTML;
assert.equal((html.match(/<details class="real-estate-texture-row"/g)||[]).length,2);
assert.equal((html.match(/<summary class="real-estate-texture-heading"/g)||[]).length,2);
assert.equal((html.match(/class="real-estate-texture-body"/g)||[]).length,2);
assert.equal((html.match(/<\/details>/g)||[]).length,2);
assert.doesNotMatch(html, /<details class="real-estate-texture-row"[^>]*\sopen>/);
// Emulate user opening both independent editors in the browser.
for(const part of ['roof','plants']) html=html.replace(`data-texture-part="${part}" >`,`data-texture-part="${part}" open>`);
host.innerHTML=html;
assert.equal(host.querySelectorAll('.real-estate-texture-row[open]').length,2);
// Selecting the combined mode rebuilds the UI; do not collapse the chosen panel.
$('real-estate-appearance-roof').onchange({target:{value:'material_atlas'}});
assert.match(host.innerHTML, /data-texture-part="roof" open>/);
assert.match(host.innerHTML, /data-texture-part="plants" open>/);
assert.match(host.innerHTML, /id="real-estate-appearance-roof"/);
assert.match(host.innerHTML, /value="material_atlas" selected/);
// Switching house through realEstateForm(row) resets all panels to closed.
vm.runInContext("realEstateRenderTextures({slug:'house_level5_02'})",ctx);
assert.doesNotMatch(host.innerHTML, /<details class="real-estate-texture-row"[^>]*\sopen>/);
'''
        cmd = ["node", "-e", code, str(STATIC / "atlas-identity.js"),
               str(STATIC / "mesh-authoring.js"), str(STATIC / "real-estate.js")]
        result = subprocess.run(cmd, text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
