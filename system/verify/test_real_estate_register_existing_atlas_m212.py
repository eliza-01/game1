"""M212: saving a bound atlas is not a new image upload, even before publication."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock
import shutil
import subprocess
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from real_estate.store import RealEstateStore
from test_real_estate_m107 import skeleton


class RealEstateExistingAtlasSaveM212(TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.model = self.root / 'house_level2_01.fbx'
        self.model.write_bytes(b'fixture model FBX')
        self.texture = self.root / 'wall_01_32x32_atlas.png'
        Image.new('RGBA', (32, 32), (20, 30, 40, 255)).save(self.texture)
        self.store = RealEstateStore(self.root)

    def initial(self):
        with mock.patch('real_estate.store.inspect', return_value=skeleton()):
            return self.store.register({
                'houseType': 'house', 'level': 2, 'variant': '01',
                'sourcePath': str(self.model),
                'textures': {'house': str(self.texture)},
                'textureReferences': {'door': 'same:house'},
            })

    def update(self, row, **other):
        return dict({'existingSlug': row['slug'], 'houseType': 'house',
                     'level': 2, 'variant': '01', 'purchasePrice': 750,
                     'textures': {}, 'textureReferences': {}}, **other)

    def test_existing_unpublished_binding_saved_even_when_source_unreadable(self):
        original = self.initial()
        variant = original['textures']['house']['atlasVariantId']
        self.assertFalse(original['textures']['house']['atlasCurrent'])
        # The archived source became unreadable, but a price/physics edit is
        # still not an atlas registration or publication request.
        stored_path = self.root / original['textures']['house']['path']
        stored_path.write_bytes(b'not an actual PNG or JPEG')
        stale_browser_payload = self.update(original, textures={
            'house': original['textures']['house']['path'],
            'door': original['textures']['door']['path'],
        }, meshOptions={'house': {'noCollide': True}})
        with mock.patch.object(self.store.atlases, 'adopt_file', side_effect=AssertionError('unexpected atlas adopt')):
            saved = self.store.register(stale_browser_payload)
        self.assertEqual(saved['purchase_price'], 750)
        self.assertTrue(saved['meshOptions']['house']['noCollide'])
        self.assertEqual(saved['textures']['house']['atlasVariantId'], variant)
        self.assertEqual(saved['textures']['door']['atlasVariantId'], variant)
        self.assertEqual(saved['revision'], original['revision'] + 1)

    def test_explicit_variant_reference_does_not_reopen_atlas(self):
        original = self.initial()
        variant = original['textures']['house']['atlasVariantId']
        (self.root / original['textures']['house']['path']).write_bytes(b'not a PNG')
        with mock.patch.object(self.store.atlases, 'adopt_file', side_effect=AssertionError('unexpected atlas adopt')):
            saved = self.store.register(self.update(original,
                textureReferences={'house': f'atlas:{variant}', 'door': f'atlas:{variant}'}))
        self.assertEqual(saved['textures']['house']['atlasVariantId'], variant)
        self.assertEqual(saved['textures']['door']['atlasVariantId'], variant)

    def test_new_invalid_png_is_rejected_with_mesh_name(self):
        original = self.initial()
        bad = self.root / 'new_wall_01_32x32_atlas.png'
        Image.new('RGB', (32, 32), (100, 40, 20)).save(bad, format='GIF')
        with self.assertRaisesRegex(ValueError, 'house: texture must be a real PNG or JPEG file'):
            self.store.register(self.update(original, textures={'house': str(bad)}))
        self.assertEqual(self.store.get(original['slug'])['revision'], original['revision'])

    def test_ui_preserves_unpublished_binding_and_displays_it(self):
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
const ctx=vm.createContext({$,window:{game1AtlasIdentity:{
    label:(item)=>item.filename||'atlas',
    describe:(item)=>({key:item.atlasKey||'wall_01',name:'wall_01',version:'01',
        resolution:'32x32',filename:item.filename||''}),pixelArea:()=>1024
  }},localStorage:{setItem(){},getItem(){return null}},
  esc:v=>String(v??''),toast(){},request:async()=>({})});
vm.runInContext(fs.readFileSync('mesh-authoring.js','utf8'),ctx);
vm.runInContext(fs.readFileSync('real-estate.js','utf8'),ctx);
ctx.realEstateRenderAtlasLibrary=()=>{};
ctx.realEstateRenderTextures=()=>{};
ctx.realEstateRenderRigs=()=>{};
ctx.realEstateRender=()=>{};
ctx.realEstateIdentity=()=>{};
const row={slug:'house_level2_01',house_type:'house',house_level:2,variant:'01',
  meshParts:['house','door'],skeleton:{meshes:[{name:'house'},{name:'door'}]},meshOptions:{},textures:{
    house:{atlasVariantId:13,atlasCurrent:false,atlasKey:'wall_01',
      filename:'wall_01_32x32_atlas.png',path:'assets/source/texture-atlases/wall_01/32x32/wall_01_32x32_atlas.png'},
    door:{atlasVariantId:14,atlasCurrent:true,atlasKey:'door_01',
      filename:'door_01_32x32_atlas.png',path:'assets/source/texture-atlases/door_01/32x32/door_01_32x32_atlas.png'}
  }};
ctx.row=row;
vm.runInContext('realEstateState.data={items:[row],textureReferences:[],atlasCatalog:[]};realEstateForm(row)',ctx);
assert.equal(vm.runInContext('realEstateState.textureRefs.house',ctx),'atlas:13');
assert.equal(vm.runInContext('realEstateState.reuseEnabled.house',ctx),true);
assert.equal(vm.runInContext('realEstateState.textures.house',ctx),'');
assert.equal(vm.runInContext('realEstateState.textureRefs.door',ctx),'atlas:14');
assert.equal(vm.runInContext('realEstateState.textures.door',ctx),'');
const opts=vm.runInContext('realEstateReuseOptions("house")',ctx);
assert.match(opts,/value="atlas:13"/);
assert.match(opts,/bound, awaiting publication/);
const payload=vm.runInContext('realEstatePayload()',ctx);
assert.equal(payload.textureReferences.house,'atlas:13');
assert.equal(payload.textures.house,'');
assert.equal(payload.textureReferences.door,'atlas:14');
'''
        result = subprocess.run([node, '-e', script], cwd=ROOT / 'system/control-center/static',
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
