"""M207: CollisionFidelity follows CanCollide, independent of mesh naming."""
from __future__ import annotations

import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from real_estate.store import mesh_options


class RealEstatePreciseIfCollidableM207(unittest.TestCase):
    def test_legacy_overrides_are_normalized_for_every_collidable_name(self):
        names = ('house', 'restoration', 'door', 'window_frames_glass', 'COL_Floor')
        for legacy in ('Default', 'Box', 'Hull', 'PreciseConvexDecomposition'):
            options = {name: {'noCollide': False, 'collisionFidelity': legacy} for name in names}
            result = mesh_options(names, options)
            for name in names:
                with self.subTest(name=name, legacy=legacy):
                    self.assertFalse(result[name]['noCollide'])
                    self.assertEqual(result[name]['collisionFidelity'], 'PreciseConvexDecomposition')

    def test_noncollidable_custom_fidelity_preserved(self):
        options = mesh_options(['house', 'door'], {
            'house': {'noCollide': True, 'collisionFidelity': 'Hull'},
            'door': {'noCollide': True, 'collisionFidelity': 'Default'},
        })
        self.assertEqual(options['house']['collisionFidelity'], 'Hull')
        self.assertEqual(options['door']['collisionFidelity'], 'Default')

    def test_studio_enforces_physics_even_with_stale_payload(self):
        source = (ROOT / 'system/studio-plugin/modules/StudioRealEstateCollisionPolicy.luau').read_text('utf8')
        self.assertIn('local fidelity = if not noCollide then "PreciseConvexDecomposition" else settings.collisionFidelity', source)
        self.assertIn('mesh.CollisionFidelity = FIDELITY[fidelity]', source)
        for importer in ('StudioRealEstateModel.luau', 'StudioRealEstatePartSync.luau'):
            self.assertIn('Collision', (ROOT / 'system/studio-plugin/modules' / importer).read_text('utf8'))

    @unittest.skipUnless(shutil.which('node'), 'Node required')
    def test_ui_live_toggle_and_payload_normalize_stale_settings(self):
        js = ROOT / 'system/control-center/static/real-estate.js'
        atlas = ROOT / 'system/control-center/static/atlas-identity.js'
        script = r"""
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const nodes=Object.create(null);
function $(id){return nodes[id]??(nodes[id]={hidden:true,innerHTML:'',textContent:'',value:'',disabled:false,addEventListener:()=>{}});}
const ctx=vm.createContext({$,esc:s=>String(s||''),window:{},toast:()=>{},request:async()=>{},console});
vm.runInContext(fs.readFileSync(process.argv[2],'utf8'),ctx);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),ctx);
assert.equal(vm.runInContext(`realEstateEffectiveFidelity('house',{noCollide:false,collisionFidelity:'Default'})`,ctx),'PreciseConvexDecomposition');
vm.runInContext(`realEstateState.inspect={analysis:{meshes:[{name:'house'},{name:'door'}]},textures:[]}; realEstateState.data={textureReferences:[]};
  realEstateState.meshOptions={house:{noCollide:false,collisionFidelity:'Default'},door:{noCollide:false,collisionFidelity:'Hull'}};
  realEstateRenderTextures();`,ctx);
const opts=vm.runInContext('realEstateState.meshOptions',ctx);
assert.equal(opts.house.collisionFidelity,'PreciseConvexDecomposition');
assert.equal(opts.door.collisionFidelity,'PreciseConvexDecomposition');
assert.match($('real-estate-mesh-textures').innerHTML,/id="real-estate-fidelity-house"[^>]*disabled/);
// Enabling No Collide unlocks custom fidelity; turning collision back on forces Precise.
$('real-estate-nocollide-house').onchange({target:{checked:true}});
assert.equal($('real-estate-fidelity-house').disabled,false);
$('real-estate-fidelity-house').onchange({target:{value:'Box'}});
assert.equal(opts.house.collisionFidelity,'Box');
$('real-estate-nocollide-house').onchange({target:{checked:false}});
assert.equal(opts.house.collisionFidelity,'PreciseConvexDecomposition');
assert.equal($('real-estate-fidelity-house').disabled,true);
assert.equal($('real-estate-fidelity-house').value,'PreciseConvexDecomposition');
// A stale caller cannot inject a collidable Default through the request payload.
opts.house.collisionFidelity='Default';
ctx['realEstateParts']=()=>['house'];
const data=vm.runInContext(`(()=>{const s=realEstateState;s.textureRefs={house:''};s.textures={house:'file.png'};s.reuseEnabled={house:false};return realEstatePayload()})()`,ctx);
assert.equal(data.meshOptions.house.collisionFidelity,'PreciseConvexDecomposition');
"""
        completed = subprocess.run(['node','-e',script,str(js),str(atlas)], capture_output=True, text=True, timeout=15)
        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == '__main__':
    unittest.main()
