"""M453: FBX MeshPart authoring uses collapsed rows without changing their contracts."""
from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / 'system' / 'control-center' / 'static'


class CompactFbxMeshRows(unittest.TestCase):
    def test_collapsed_rows_styled_like_house_parts(self):
        css = (STATIC / 'deco-assets.css').read_text(encoding='utf-8')
        self.assertIn('.deco-fbx-mesh[open] > .deco-fbx-mesh-title::before', css)
        self.assertIn('.deco-fbx-mesh-title:focus-visible', css)
        self.assertIn('.deco-fbx-mesh-body {display:grid;', css)

    @unittest.skipUnless(shutil.which('node'), 'Node is required for UI regression test')
    def test_compact_rows_controls_skeleton_and_expansion_state(self):
        code = r'''
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const esc = value => String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('"', '&quot;');
const window = {game1ConsumerAtlasEditor:{sections:()=>[]}};
const ctx = vm.createContext({window,esc});
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),ctx);
const ui = window.game1MeshAuthoring;
const names = ['blades','body','door','fabric','rig_carrier','roof','wood'];
const meshes = names.map(name=>({name,vertices:name==='blades'?344:28,
  armature:name==='door'||name==='rig_carrier'?'windmill_armature':null,
  bones:name==='door'?[{name:'windmill_door_socket'}]:[],
  influencedBones:name==='door'?['windmill_door_socket']:[]}));
const analysis = {meshes,armatures:[{name:'windmill_armature'}]};
const visual = {materials:[{id:'Plastic',label:'Plastic'}],atlases:[]};
const options = {blades:{noCollide:true,glass:false,collisionFidelity:'Hull',doubleSided:false},
  fabric:{appearanceMode:'material',visualMaterial:'Plastic',visualColor:'#FFFFFF'}};
const html = ui.inspectionView(analysis,options,'location-mesh',visual);
assert.equal((html.match(/<details class="deco-fbx-mesh"/g)||[]).length,7);
assert.equal((html.match(/<summary class="deco-fbx-mesh-title"/g)||[]).length,7);
assert.equal((html.match(/<div class="deco-fbx-mesh-body">/g)||[]).length,7);
assert.doesNotMatch(html, /<details class="deco-fbx-mesh"[^>]*\sopen>/);
for(const name of names) assert.match(html,new RegExp('data-fbx-mesh="'+name+'"'));
assert.match(html, /data-fbx-mesh="blades"[\s\S]*?344 vertices/);
assert.match(html, /data-mesh-field="noCollide" checked/);
assert.match(html, /data-mesh-field="collisionFidelity"/);
assert.match(html, /data-mesh-visual="appearanceMode"/);
assert.match(html, /<details class="deco-fbx-skeleton"><summary>windmill_armature/);
const carrier = html.split('data-fbx-mesh="rig_carrier"')[1].split('data-fbx-mesh="roof"')[0];
assert.match(carrier, /Authored carrier/);
assert.doesNotMatch(carrier, /data-mesh-field|data-mesh-visual/);
const source = {querySelectorAll:s=>{
  assert.equal(s,'.deco-fbx-mesh[open]');
  return [{dataset:{fbxMesh:'fabric'}},{dataset:{fbxMesh:'door'}}];
}};
const expanded = ui.openMeshNames(source);
const rerender = ui.inspectionView(analysis,options,'location-mesh',visual,expanded);
assert.match(rerender,/data-fbx-mesh="fabric" open>/);
assert.match(rerender,/data-fbx-mesh="door" open>/);
assert.doesNotMatch(rerender,/data-fbx-mesh="blades" open>/);
// Existing per-MeshPart state and change callback still work inside <details>.
const control = {dataset:{meshField:'noCollide'},checked:false};
const fidelity = {value:'Hull',disabled:true};
const status = {textContent:''};
const row = {dataset:{fbxMesh:'blades'},querySelector:s=>
  s==='[data-mesh-visual="appearanceMode"]'?null:
  s==='[data-mesh-field="collisionFidelity"]'?fidelity:
  s==='[data-mesh-status]'?status:null,
  querySelectorAll:s=>s==='[data-mesh-field]'?[control]:[]};
let calls=0;
ui.wire({querySelectorAll:s=>s==='[data-fbx-mesh]'?[row]:[]},options,()=>calls++);
control.onchange();
assert.equal(options.blades.noCollide,false);
assert.equal(options.blades.collisionFidelity,'Hull');
assert.match(status.textContent,/CanCollide: true/);
assert.equal(calls,1);
assert.equal(fidelity.disabled,false);
'''
        result = subprocess.run(
            ['node', '-e', code, str(STATIC / 'mesh-authoring.js')],
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_both_location_editors_remember_expanded_meshes(self):
        for name in ('deco-assets.js', 'location-asset-workflow.js'):
            source = (STATIC / name).read_text(encoding='utf-8')
            self.assertIn('game1MeshAuthoring.openMeshNames(', source)
            self.assertIn('expandedMeshes)', source)


if __name__ == '__main__':
    unittest.main()
