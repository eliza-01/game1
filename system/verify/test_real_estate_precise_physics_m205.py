"""M205: editable, persistent Real Estate physics defaults and one Studio writer."""
from __future__ import annotations

import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from real_estate.collision_policy import default_no_collide, default_collision_fidelity
from real_estate.store import mesh_options


class RealEstatePhysicsM205(unittest.TestCase):
    def test_per_mesh_default_contract(self):
        physical = ('door', 'door_01', 'window_frames_glass', 'glass_panel', 'COL_Floor', 'house_col', 'wall_COL_01')
        visual = ('house', 'restoration', 'structures_01', 'window_frames')
        for name in physical:
            with self.subTest(name=name):
                self.assertFalse(default_no_collide(name))
                self.assertEqual(default_collision_fidelity(name), 'PreciseConvexDecomposition')
        for name in visual:
            with self.subTest(name=name):
                self.assertTrue(default_no_collide(name))
                self.assertEqual(default_collision_fidelity(name), 'Box')
        effective = mesh_options([*physical, *visual], {})
        for part, flags in effective.items():
            self.assertFalse(flags['doubleSided'], part)
            self.assertEqual(flags['collisionFidelity'], default_collision_fidelity(part))
            self.assertEqual(flags['noCollide'], default_no_collide(part))

    def test_persisted_overrides_and_invalid_values(self):
        custom = mesh_options(['door', 'house', 'col_mesh'], {
            'door': {'noCollide': True, 'collisionFidelity': 'Hull', 'doubleSided': False},
            'house': {'noCollide': False, 'collisionFidelity': 'PreciseConvexDecomposition'},
            'col_mesh': {'noCollide': True, 'collisionFidelity': 'Box'},
        })
        self.assertEqual(custom['door']['collisionFidelity'], 'Hull')
        self.assertTrue(custom['door']['noCollide'])
        self.assertFalse(custom['door']['doubleSided'])
        self.assertFalse(custom['house']['noCollide'])
        self.assertEqual(custom['house']['collisionFidelity'], 'PreciseConvexDecomposition')
        self.assertTrue(custom['col_mesh']['noCollide'])
        self.assertEqual(custom['col_mesh']['collisionFidelity'], 'Box')
        # M207: an old explicit Default/Box/Hull can never persist on a
        # collidable part, including a visual mesh manually made physical.
        legacy = mesh_options(['door', 'house', 'wall_COL_01'], {
            'door': {'noCollide': False, 'collisionFidelity': 'Default'},
            'house': {'noCollide': False, 'collisionFidelity': 'Box'},
            'wall_COL_01': {'noCollide': False, 'collisionFidelity': 'Hull'},
        })
        self.assertTrue(all(v['collisionFidelity'] == 'PreciseConvexDecomposition'
                            for v in legacy.values()))
        with self.assertRaisesRegex(ValueError, 'invalid CollisionFidelity'):
            mesh_options(['door'], {'door': {'collisionFidelity': 'Magic'}})

    def test_studio_policy_applies_identical_authoring_options_everywhere(self):
        source = (ROOT / 'system/studio-plugin/modules/StudioRealEstateCollisionPolicy.luau').read_text('utf8')
        core = (ROOT / 'src/shared/world/MeshPhysicsCore.luau').read_text('utf8')
        self.assertIn('Core.Apply(mesh, not noCollide, fidelity,', source)
        self.assertIn('CollectionService:AddTag(mesh, COLLIDER_TAG)', source)
        for expected in ('mesh.CanCollide = true', 'mesh.CanCollide = false',
                         'mesh.CanQuery = true', 'mesh.CanQuery = false',
                         'mesh.CanTouch = false', 'mesh.CollisionFidelity = Core.Fidelity(if canCollide then "PreciseConvexDecomposition" else fidelity)',
                         'mesh.DoubleSided = doubleSided'):
            self.assertIn(expected, core)
        for name in ('StudioRealEstateModel', 'StudioRealEstatePartSync'):
            self.assertIn('CollisionPolicy' if name.endswith('Model') else 'Collision.Apply',
                (ROOT / f'system/studio-plugin/modules/{name}.luau').read_text('utf8'))

    @unittest.skipUnless(shutil.which('node'), 'Node required')
    def test_visible_settings_editor_and_payload_for_all_meshes(self):
        js = ROOT / 'system/control-center/static/real-estate.js'
        atlas = ROOT / 'system/control-center/static/atlas-identity.js'
        code = r'''
const fs=require('fs'), vm=require('vm'), assert=require('node:assert/strict');
const nodes=Object.create(null);
function $(id){return nodes[id]??(nodes[id]={hidden:true,innerHTML:'',textContent:'',value:'',addEventListener:()=>{}});}
const ctx=vm.createContext({$,esc:s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;'),
  window:{},request:async()=>{},toast:()=>{},console});
vm.runInContext(fs.readFileSync(process.argv[2],'utf8'),ctx);
vm.runInContext(fs.readFileSync(process.argv[3],'utf8'),ctx);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),ctx);
vm.runInContext(`realEstateState.inspect={analysis:{meshes:[{name:'house'},{name:'door'},
  {name:'window_frames_glass'},{name:'wall_COL_01'}]},textures:[]};
realEstateState.data={textureReferences:[]}; realEstateRenderTextures();`,ctx);
const html=$('real-estate-mesh-textures').innerHTML;
for(const part of ['house','door','window_frames_glass','wall_COL_01']){
  assert.match(html,new RegExp('id="real-estate-fidelity-'+part+'"'));
  assert.match(html,new RegExp('id="real-estate-doublesided-'+part+'"'));
  assert.match(html,new RegExp('id="real-estate-physics-state-'+part+'"'));
}
// Collision-enabled parts show a locked Precise selector, even with old saved choices.
assert.match(html,/id="real-estate-fidelity-door"[^>]*disabled/);
assert.match(html,/id="real-estate-fidelity-wall_COL_01"[^>]*disabled/);
const opts=vm.runInContext('realEstateState.meshOptions',ctx);
for(const part of ['door','window_frames_glass','wall_COL_01']){
  assert.equal(opts[part].noCollide,false);
  assert.equal(opts[part].collisionFidelity,'PreciseConvexDecomposition');
  assert.equal(opts[part].doubleSided,false);
}
assert.equal(opts.house.noCollide,true);
assert.equal(opts.house.collisionFidelity,'Box');
$('real-estate-nocollide-door').onchange({target:{checked:true}});
$('real-estate-fidelity-door').onchange({target:{value:'Hull'}});
$('real-estate-doublesided-door').onchange({target:{checked:false}});
assert.equal(opts.door.collisionFidelity,'Hull');
assert.equal(opts.door.doubleSided,false);
assert.equal(opts.door.noCollide,true);
assert.match($('real-estate-physics-state-door').textContent,/CanQuery: false/);
vm.runInContext('realEstateRender=()=>{}',ctx);
vm.runInContext(`realEstateForm({slug:'example',meshParts:['door','house'],meshOptions:{
  door:{noCollide:true,collisionFidelity:'Hull',doubleSided:false},
  house:{noCollide:true,collisionFidelity:'Box',doubleSided:true}}});`,ctx);
const saved=vm.runInContext('realEstateState.meshOptions.door',ctx);
assert.equal(saved.noCollide,true);
assert.equal(saved.collisionFidelity,'Hull');
assert.equal(saved.doubleSided,false);
'''
        completed = subprocess.run(['node', '-e', code, str(js), str(atlas),str(ROOT / 'system/control-center/static/mesh-authoring.js')], capture_output=True,
                                   text=True, timeout=15)
        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == '__main__':
    unittest.main()
