"""M374: deleted estate models can be re-registered using saved Plot type identity."""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless
from unittest.mock import patch
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from api import real_estate
from real_estate.placement import RealEstatePlacementStore
from real_estate.store import RealEstateStore


def cf(x=0, y=0, z=0):
    return [x, y, z, 1, 0, 0, 0, 1, 0, 0, 0, 1]


def capture(slug, index):
    return {
        'schemaVersion': 2, 'houseSlug': slug, 'plotIndex': index,
        'plotVolume': f'plot_{index:02d}_volume',
        'worldCFrame': cf(15, 0, 6), 'plotCFrame': cf(10, 0, 0),
        'localCFrame': cf(5, 0, 6), 'houseAnchorLocalCFrame': cf(),
        'houseAnchorWorldCFrame': cf(15, 0, 6), 'scale': 1.0,
    }


def new_rig(part):
    return {'schemaVersion': 1, 'meshes': [
        {'name': part, 'armature': 'house_armature', 'vertices': 12,
         'bones': [{'name': 'houseplant_01', 'parent': '',
                    'matrixLocal': [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]}],
         'influencedBones': []},
    ]}


class HouseReregisterFromPlot(TestCase):
    def test_model_delete_and_new_registration_keep_all_plot_pivots(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = root / 'incoming'
            folder.mkdir()
            first = folder / 'house_level5_01.fbx'
            second = folder / 'house_level5_01_remesh.fbx'
            first.write_bytes(b'old-model')
            second.write_bytes(b'new-model-with-different-meshes')
            houses = RealEstateStore(root)
            plots = RealEstatePlacementStore(root, houses)

            def payload(file):
                return {'houseType': 'house', 'level': 5, 'variant': '01',
                        'sourcePath': str(file), 'purchasePrice': 100,
                        'salePrice': 50, 'minLevel': 5,
                        'textures': {}, 'textureReferences': {}, 'meshOptions': {}}

            def response():
                status, data = real_estate.read(urlparse('/api/real-estate'), {
                    'real_estate': houses, 'real_estate_placements': plots,
                    'publication_config': lambda: {'configured': False},
                })
                self.assertEqual(status, 200)
                return data

            with patch('real_estate.store.inspect', return_value=new_rig('old_shell')):
                houses.register(payload(first))
            for index in (1, 5, 39):
                plots.bind('house_level5_01', index, capture('house_level5_01', index))
            before = plots.snapshot()['items']
            self.assertEqual(response()['unregisteredPlotTypes'], [])
            houses.delete('house_level5_01')
            self.assertIsNone(houses.get('house_level5_01'))
            self.assertEqual(response()['unregisteredPlotTypes'], [
                {'slug': 'house_level5_01', 'plotCount': 3},
            ])
            with patch('real_estate.store.inspect', return_value=new_rig('stone_walls')):
                fresh = houses.register(payload(second))
            self.assertEqual(fresh['slug'], 'house_level5_01')
            self.assertIn('stone_walls', fresh['meshParts'])
            self.assertNotIn('old_shell', fresh['meshParts'])
            self.assertFalse(fresh['model_asset_id'])  # No stale Roblox publication ID
            self.assertEqual(plots.snapshot()['items'], before)
            self.assertEqual(response()['unregisteredPlotTypes'], [])

    @skipUnless(shutil.which('node'), 'Node.js required for Real Estate UI contract')
    def test_restore_button_preserves_identity_through_fbx_selection(self):
        script = r'''
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
let restoreNode={dataset:{reRegister:'house_level5_01'},focus(){}};
const elements=new Map();
const $=id=>{
  if(!elements.has(id))elements.set(id,{innerHTML:'',textContent:'',hidden:true,
    value:'',disabled:false,focus(){this.focused=true},addEventListener(){},
    querySelectorAll(sel){return id==='real-estate-tree'&&sel==='[data-re-register]'?[restoreNode]:[]}});
  return elements.get(id);
};
const ctx=vm.createContext({$,esc:v=>String(v??''),window:{},request(){},toast(){},
  localStorage:{getItem(){return null},setItem(){}}});
vm.runInContext(fs.readFileSync('real-estate.js','utf8'),ctx);
vm.runInContext(`
realEstateState.data={publication:{configured:false},items:[],
  unregisteredPlotTypes:[{slug:'house_level5_01',plotCount:39}]};
realEstateForm=()=>{realEstateState.selected=null;realEstateState.registrationTarget=null;};
realEstateRender();`,ctx);
assert.match($('real-estate-tree').innerHTML,/house_level5_01 · 39 plots · Register again/);
assert.equal(typeof restoreNode.onclick,'function');
restoreNode.onclick();
assert.equal($('real-estate-level').value,'5');
assert.equal($('real-estate-variant').value,'01');
assert.equal($('real-estate-slug').textContent,'house_level5_01');
assert.equal($('real-estate-choose').focused,true);
ctx.request=async path=>path==='/api/files/choose-real-estate-model'
  ? {path:'house_level5_01_remesh.fbx'}
  : {sourcePath:'house_level5_01_remesh.fbx',houseType:'house',level:1,
     variant:'02',analysis:{meshes:[]},warnings:[]};
vm.runInContext('realEstateRenderRigs=()=>{}; realEstateRenderTextures=()=>{}',ctx);
(async()=>{
  assert.equal(await vm.runInContext('realEstateChooseFbx()',ctx),true);
  assert.equal($('real-estate-level').value,'5');
  assert.equal($('real-estate-variant').value,'01');
  assert.equal($('real-estate-slug').textContent,'house_level5_01');
})().catch(error=>{console.error(error);process.exitCode=1});
'''
        result = subprocess.run(['node', '-e', script],
            cwd=ROOT/'system/control-center/static',
            text=True, encoding='utf-8', capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    import unittest
    unittest.main()
