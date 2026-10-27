"""M135: Real Estate mesh texture controls remain legible and independent."""
from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CSS = ROOT / 'system/control-center/static/real-estate.css'
JS = ROOT / 'system/control-center/static/real-estate.js'
HTML = ROOT / 'system/control-center/static/index.html'


class RealEstateMeshEditorM135(unittest.TestCase):
    def test_layout_has_no_fixed_mesh_name_column(self):
        css = CSS.read_text(encoding='utf-8')
        page = HTML.read_text(encoding='utf-8')
        self.assertIn('real-estate-mesh-switches', css)
        self.assertIn('display:flex; flex-direction:column;', css)
        self.assertIn('.real-estate-mesh-name', css)
        self.assertIn('overflow-wrap:anywhere', css)
        self.assertNotIn('grid-template-columns:112px', css)
        self.assertIn('COL_', page)
        self.assertIn('physics-only', page)

    @unittest.skipUnless(shutil.which('node'), 'Node required for JS UI behavior test')
    def test_rendered_control_structure_and_checkbox_behavior(self):
        # Exercise the actual renderer without a browser/network, using lightweight DOM stubs.
        code = r'''
const fs = require('fs');
const vm = require('vm');
const assert = require('node:assert/strict');
const nodes = Object.create(null);
function $(id){return nodes[id]??(nodes[id]={hidden:true,innerHTML:'',textContent:'',value:'',addEventListener:()=>{}});}
const ctx = vm.createContext({$,esc:s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;'),window:{},request:async()=>{},toast:()=>{},console});
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),ctx);
vm.runInContext(`realEstateState.inspect={analysis:{meshes:[{name:'house'},{name:'col_mesh'},{name:'door'},{name:'restoration'},{name:'window_frames_glass'}]},textures:[{name:'house_level4_01_4096x4096_atlas.png',path:'C:/textures/house_level4_01_4096x4096_atlas.png'}]};realEstateState.data={textureReferences:[]};realEstateRenderTextures()`,ctx);
const html=$('real-estate-mesh-textures').innerHTML;
assert.equal((html.match(/class="real-estate-texture-row/g)||[]).length,5);
assert.equal((html.match(/class="real-estate-mesh-switches"/g)||[]).length,5);
assert.match(html,/class="real-estate-mesh-name">window_frames_glass/);
assert.match(html,/Collision · no texture/);
assert.doesNotMatch(html,/id="real-estate-texture-col_mesh"/);
assert.match(html,/id="real-estate-nocollide-col_mesh" >/);
assert.match(html,/id="real-estate-nocollide-house" checked/);
assert.match(html,/id="real-estate-glass-window_frames_glass" checked/);
$('real-estate-nocollide-house').onchange({target:{checked:false}});
$('real-estate-reuse-door').onchange({target:{checked:true}});
const state=vm.runInContext('({house:realEstateState.meshOptions.house,doorReuse:realEstateState.reuseEnabled.door})',ctx);
assert.equal(state.house.noCollide,false);
assert.equal(state.doorReuse,true);
assert.equal($('real-estate-owned-door').hidden,true);
assert.equal($('real-estate-shared-door').hidden,false);
'''
        done = subprocess.run(['node', '-e', code, str(JS)], capture_output=True, text=True, timeout=15)
        self.assertEqual(done.returncode, 0, done.stderr)


if __name__ == '__main__':
    unittest.main()
