"""M183: inspect reflects M182 publication ownership; atlases follow houses."""
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from real_estate.rig_publication_policy import publish_bones_for_mesh


class RealEstateInspectionM183(unittest.TestCase):
    def test_source_bones_are_distinct_from_published_bones(self):
        bones = [{'name': name} for name in ('chest_01_socket', 'land_spawn_01_socket')]
        cases = [
            ({'name': 'house', 'armature': 'house_armature', 'bones': bones, 'influencedBones': []}, 2),
            ({'name': 'door', 'armature': 'door_armature', 'bones': bones, 'influencedBones': ['chest_01_socket']}, 2),
            ({'name': 'window_frames_glass', 'armature': 'house_armature', 'bones': bones, 'influencedBones': []}, 0),
            ({'name': 'structures_01', 'armature': 'house_armature', 'bones': bones, 'influencedBones': ['chest_01_socket']}, 2),
            ({'name': 'decor', 'armature': 'decor_armature', 'bones': bones, 'influencedBones': []}, 2),
        ]
        for part, expected in cases:
            with self.subTest(name=part['name']):
                self.assertEqual(len(publish_bones_for_mesh(part)), expected)
                self.assertEqual(len(part['bones']), 2, 'source manifest must not be modified')

    def test_atlas_registry_is_below_registered_houses(self):
        html = (ROOT / 'system/control-center/static/index.html').read_text(encoding='utf-8')
        real_estate = html.split('id="real-estate-view"', 1)[1].split('id="locations-view"', 1)[0]
        self.assertEqual(real_estate.count('id="real-estate-atlas-rows"'), 1)
        self.assertEqual(real_estate.count('id="real-estate-library-rows"'), 1)
        self.assertLess(real_estate.index('id="real-estate-library-rows"'), real_estate.index('id="real-estate-atlas-rows"'))
        self.assertIn('real-estate.js?v=24', html)

    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for browser JS test')
    def test_renderer_shows_published_bones_not_shared_source_duplicates(self):
        code = r'''
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const elements=Object.create(null);
const $=id=>elements[id]??(elements[id]={innerHTML:'',hidden:true,textContent:'',value:'',addEventListener(){}});
const esc=value=>String(value??'').replace(/&/g,'&amp;').replace(/</g,'&lt;');
const ctx=vm.createContext({$,esc,window:{},localStorage:{setItem(){},getItem(){return null;}},request(){},toast(){}});
vm.runInContext(fs.readFileSync(process.argv[2],'utf8'),ctx);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),ctx);
const names=['chest_01_socket','land_spawn_01_socket'];
const bones=names.map(name=>({name,parent:'',matrixLocal:[]}));
const part=(name,armature,influencedBones=[])=>({name,armature,bones,influencedBones});
const cases=[
 [part('house','house_armature'),2],
 [part('door','door_armature',['chest_01_socket']),2],
 [part('col_mesh','house_armature'),0],
 [part('restoration','house_armature'),0],
 [part('structures_01','house_armature'),0],
 [part('window_frames_glass','house_armature'),0],
 [part('weighted_detail','house_armature',['chest_01_socket']),2],
 [part('custom','detail_armature'),2],
 [part('loose','',[]),2]
];
for(const [mesh,expected] of cases){
 const got=vm.runInContext('realEstatePublishedBones',ctx)(mesh);
 assert.equal(got.length,expected,mesh.name);
}
const source=cases.slice(0,6).map(([mesh])=>mesh);
vm.runInContext('realEstateRenderRigs',ctx)({meshes:source},[]);
assert.match($('real-estate-rig').textContent,/house: 2 костей при публикации/);
assert.match($('real-estate-rig').textContent,/structures_01: 0 костей при публикации/);
assert.match($('real-estate-rig').textContent,/door: 2 костей при публикации/);
const html=$('real-estate-bone-list').innerHTML;
assert.equal((html.match(/<code>land_spawn_01_socket<\/code>/g)||[]).length,2,
 'only house and door own source bones in this artificial example');
assert.equal((html.match(/В Model Asset этой статичной части они не экспортируются/g)||[]).length,4);
assert.doesNotMatch(html,/Independent rig/);
assert.equal($('real-estate-rig-warnings').hidden,true);
'''
        result = subprocess.run(
            [shutil.which('node'), '-e', code,
             str(ROOT / 'system/control-center/static/real-estate.js'),
             str(ROOT / 'system/control-center/static/mesh-authoring.js')],
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
