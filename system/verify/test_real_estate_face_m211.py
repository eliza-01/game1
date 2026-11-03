"""M211: independent checks for Real Estate saves and face pose composition."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock
import subprocess
import shutil
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from real_estate.store import RealEstateStore
from test_real_estate_m107 import skeleton


class RealEstateSaveAndFaceM211(TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.model = self.root / 'house_level2_01.fbx'
        self.model.write_bytes(b'fixture model FBX')
        self.texture = self.root / 'wall_01_32x32_atlas.png'
        Image.new('RGBA', (32, 32), (20, 30, 40, 255)).save(self.texture)
        self.store = RealEstateStore(self.root)

    def payload(self):
        return dict(houseType='house', level=2, variant='01',
                    sourcePath=str(self.model), textures={'house':str(self.texture)},
                    textureReferences={'door':'same:house'})

    def test_existing_house_without_atlas_on_legacy_mesh_can_save_physics(self):
        with mock.patch('real_estate.store.inspect', return_value=skeleton()):
            first = self.store.register(self.payload())
        self.store.atlases.unbind('real_estate', f"{first['slug']}:door")
        update = dict(existingSlug=first['slug'], houseType='house', level=2, variant='01',
                      textures={}, textureReferences={},
                      meshOptions={'door':{'noCollide':True}}, purchasePrice=500)
        saved = self.store.register(update)
        self.assertEqual(saved['purchase_price'], 500)
        self.assertTrue(saved['meshOptions']['door']['noCollide'])
        self.assertIsNone(saved['textures']['door']['atlasVariantId'])
        self.assertEqual(saved['textures']['house']['atlasVariantId'], first['textures']['house']['atlasVariantId'])

    def test_new_house_without_atlas_for_visual_mesh_is_still_rejected(self):
        payload = self.payload()
        payload['textureReferences'] = {}
        with mock.patch('real_estate.store.inspect', return_value=skeleton()):
            with self.assertRaisesRegex(ValueError, 'door: choose an atlas source or registered variant'):
                self.store.register(payload)

    def test_ui_handles_no_selected_house_and_surfaces_http_validation(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node.js unavailable')
        script = r'''
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const elements=new Map();
const $=id=>{
  if(!elements.has(id))elements.set(id,{value:'',textContent:'',innerHTML:'',hidden:true,
    disabled:false,querySelectorAll(){return []},addEventListener(){}});
  return elements.get(id);
};
const errors=[];
const ctx=vm.createContext({$,window:{},localStorage:{setItem(){},getItem(){return null}},
  esc:v=>String(v??''),toast:v=>errors.push(v),request:async()=>{throw Error('door: missing atlas')} });
vm.runInContext(fs.readFileSync('real-estate.js','utf8'),ctx);
ctx.realEstateRenderAtlasLibrary=()=>{};ctx.realEstateRenderTextures=()=>{};
ctx.realEstateRenderRigs=()=>{};ctx.realEstateIdentity=()=>{};
vm.runInContext('realEstateState.data={publication:{configured:true},items:[]};realEstateForm(null)',ctx);
assert.equal($('real-estate-register-error').hidden,true);
assert.match($('real-estate-publish-status').textContent,/register a house first/);
vm.runInContext('realEstateState.publicationJob={slug:"old_house",status:"failed"};realEstateRender()',ctx);
assert.match($('real-estate-publish-status').textContent,/register a house first/);
(async()=>{
  assert.equal(await vm.runInContext('realEstateRegister()',ctx),false);
  assert.equal($('real-estate-register-error').hidden,false);
  assert.match($('real-estate-register-error').textContent,/door: missing atlas/);
  assert.equal($('real-estate-register').disabled,false);
})().catch(e=>{console.error(e);process.exitCode=1});
'''
        result = subprocess.run([node, '-e', script], cwd=ROOT/'system/control-center/static',
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)

    def test_face_copy_updates_after_attack_composition(self):
        face = (ROOT/'src/client/character/animation/FaceAnimationController.luau').read_text()
        attack = (ROOT/'src/client/character/animation/AttackUpperBodyComposer.luau').read_text()
        self.assertIn('RunService.PreSimulation:Connect(step)', attack)
        self.assertIn('RunService.PostSimulation:Connect(function(delta)', face)
        self.assertNotIn('RunService.PreSimulation:Connect(function(delta)', face)
