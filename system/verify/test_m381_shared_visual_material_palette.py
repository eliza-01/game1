"""M381: one Roblox material catalog, validator, and Studio material conversion."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from api.real_estate import read as estate_read
from real_estate.store import mesh_options
from services import mesh_visual_appearance as appearance

# Creator Hub / enums/Material: 45 values including Air and Water (Terrain-only).
EXPECTED = {
    'Plastic', 'SmoothPlastic', 'Neon', 'Wood', 'WoodPlanks', 'Marble',
    'Basalt', 'Slate', 'CrackedLava', 'Concrete', 'Limestone', 'Granite',
    'Pavement', 'Brick', 'Pebble', 'Cobblestone', 'Rock', 'Sandstone',
    'CorrodedMetal', 'DiamondPlate', 'Foil', 'Metal', 'Grass',
    'LeafyGrass', 'Sand', 'Fabric', 'Snow', 'Mud', 'Ground', 'Asphalt',
    'Salt', 'Ice', 'Glacier', 'Glass', 'ForceField', 'Cardboard',
    'Carpet', 'CeramicTiles', 'ClayRoofTiles', 'RoofShingles',
    'Leather', 'Plaster', 'Rubber',
}


class SharedVisualMaterialPalette(unittest.TestCase):
    def test_official_basepart_palette_without_terrain_only(self):
        self.assertEqual(set(appearance.BASEPART_MATERIALS), EXPECTED)
        self.assertEqual(len(appearance.BASEPART_MATERIALS), 43)
        self.assertEqual(len(set(appearance.BASEPART_MATERIALS)), 43)
        self.assertTrue(appearance.options()[-1]['id'] == 'Rubber')
        self.assertEqual([x['id'] for x in appearance.options() if x['requiresTexture']], ['ForceField'])
        for excluded in ('Air', 'Water'):
            self.assertNotIn(excluded, EXPECTED)

    def test_shared_validator_controls_location_and_each_house_part(self):
        new_names = ('Cardboard', 'Carpet', 'CeramicTiles', 'ClayRoofTiles',
                     'RoofShingles', 'Leather', 'Plaster', 'Rubber', 'Pebble')
        raw = {name: {'appearanceMode': 'material', 'visualMaterial': name,
                      'visualColor': '#ab12ef'} for name in new_names}
        resolved = mesh_options(new_names, raw)
        for name in new_names:
            self.assertEqual(appearance.validated('material', name, '#ab12ef'),
                             ('material', name, '#AB12EF'))
            self.assertEqual(resolved[name]['visualMaterial'], name)
            self.assertEqual(resolved[name]['visualColor'], '#AB12EF')
            self.assertFalse(resolved[name]['alphaEnabled'])
        for name in ('NoSuchMaterial', 'Water', 'Air', 'ForceField'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                mesh_options(('wall',), {'wall': {'visualMaterial': name}})
        with self.assertRaisesRegex(ValueError, 'requires an atlas'):
            mesh_options(('wall',), {'wall': {'alphaEnabled': True}})

    def test_new_location_material_persists_without_atlas(self):
        from tempfile import TemporaryDirectory
        from location_asset_store import LocationAssetStore
        with TemporaryDirectory() as folder:
            root = Path(folder)
            fbx = root / 'roof_source.fbx'
            fbx.write_bytes(b'FBX placeholder for registrar')
            store = LocationAssetStore(root)
            result = store.register({
                'nameEn': 'Roof', 'slug': 'roof_test_01', 'category': 'prop',
                'modelSourcePath': str(fbx), 'appearanceMode': 'material',
                'visualMaterial': 'ClayRoofTiles', 'visualColor': '#ca925a',
            })
            self.assertEqual(result['visualMaterial'], 'ClayRoofTiles')
            self.assertEqual(result['visualColor'], '#CA925A')
            self.assertFalse(result['texture_asset_id'])
            self.assertEqual(LocationAssetStore(root).get('roof_test_01')['visualMaterial'], 'ClayRoofTiles')

    def test_estate_api_and_location_use_identical_material_metadata(self):
        class Estate:
            def snapshot(self):
                return {'schemaVersion': 2, 'items': []}
        status, payload = estate_read(
            type('URL', (), {'path': '/api/real-estate'})(),
            {'real_estate': Estate(), 'publication_config': lambda: {}})
        self.assertEqual(status, 200)
        self.assertEqual(payload['visualMaterials'], appearance.options())
        # Location Assets delegates its palette directly to the shared service.
        self.assertIn('visualMaterials=appearance.options()',
                      (ROOT / 'system/control-center/location_asset_store.py').read_text(encoding='utf8'))

    @unittest.skipUnless(shutil.which('node'), 'Node.js required for HTML editor behavior')
    def test_house_picker_renders_full_server_catalog(self):
        js = ROOT / 'system/control-center/static/real-estate.js'
        code = r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const elements=Object.create(null);
const $=id=>elements[id]??(elements[id]={value:'',innerHTML:'',hidden:false,addEventListener(){}});
const window={game1MeshAuthoring:{defaults:()=>({noCollide:true}),normalize:(_p,f)=>f,
   controls:()=>'',effectiveFidelity:()=>'',status:()=>''},game1AtlasIdentity:{describe:()=>({}),pixelArea:()=>0}};
const ctx=vm.createContext({$,window,localStorage:{getItem(){return null;},setItem(){}},
 esc:v=>String(v??''),toast(){},request(){}});
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),ctx);
vm.runInContext(`realEstateState.data={items:[], visualMaterials:JSON.parse(${JSON.stringify(process.argv[2])})};
 realEstateState.inspect={analysis:{meshes:[{name:'roof'}]},textures:[]};
 realEstateState.meshOptions.roof={noCollide:true,glass:false,doubleSided:false,collisionFidelity:'Default'};
 realEstateRenderTextures();`,ctx);
const html=elements['real-estate-mesh-textures'].innerHTML;
for(const value of ['Cardboard','Carpet','CeramicTiles','ClayRoofTiles','RoofShingles','Leather','Plaster','Rubber','Pebble'])
    assert.match(html,new RegExp(`<option value="${value}"`));
assert.match(html,/<option value="ForceField"[^>]*disabled/);
assert.doesNotMatch(html,/<option value="Air"/);
assert.doesNotMatch(html,/<option value="Water"/);
'''
        result = subprocess.run([shutil.which('node'), '-e', code,
            str(js), json.dumps(appearance.options())], capture_output=True, text=True,
            encoding='utf8', timeout=25)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_studio_appearance_logic_is_one_shared_mechanism(self):
        common = (ROOT / 'system/studio-plugin/modules/StudioTextureAppearance.luau').read_text(encoding='utf8')
        estate = (ROOT / 'system/studio-plugin/modules/StudioRealEstateAppearance.luau').read_text(encoding='utf8')
        location = (ROOT / 'system/studio-plugin/modules/StudioLocationVisualAppearance.luau').read_text(encoding='utf8')
        self.assertIn('function StudioTextureAppearance.MaterialColor(', common)
        self.assertIn('StudioTextureAppearance.MaterialColor(materialName,hex)', common)
        self.assertIn('Texture.MaterialColor(', location)
        self.assertIn('Texture.ApplyVisual(mesh,row', location)
        self.assertIn('Texture.ApplyVisual(mesh,settings', estate)
        self.assertNotIn('local function materialEnum(', location)
        self.assertNotIn('local function hexColor(', location)


if __name__ == '__main__':
    unittest.main()
