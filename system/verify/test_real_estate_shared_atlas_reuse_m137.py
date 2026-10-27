"""M137: Real Estate reuse picker must expose published central AtlasRegistry variants."""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from real_estate.store import RealEstateStore


class SharedAtlasReuseM137Tests(TestCase):
    def test_registry_exposes_published_house_atlas_without_legacy_estate_image_id(self):
        with TemporaryDirectory(prefix='m137-estate-atlas-') as tmp:
            root = Path(tmp)
            file = root / 'house_level4_01_64x64_atlas.png'
            Image.new('RGB', (64, 64), (125, 90, 40)).save(file)
            store = RealEstateStore(root)
            variant = store.atlases.register_file(str(file))
            # Simulate completed Roblox publication; never upload from a test.
            with store.atlases.connect() as db:
                db.execute('UPDATE texture_atlas_variants SET published_id=?,published_sha256=source_sha256 WHERE id=?',
                           ('92116826074029', variant['id']))
            references = store.texture_references()
            self.assertEqual(len(references), 1)
            entry = references[0]
            self.assertEqual(entry['reference'], f'atlas:{variant["id"]}')
            self.assertEqual(entry['group'], 'atlas')
            self.assertEqual(entry['filename'], file.name)
            self.assertEqual(entry['assetId'], '92116826074029')
            self.assertEqual(entry['label'], 'house_level4_01')
            # A central variant appears even before there is an Estate record.
            self.assertEqual(store.list(), [])

    @skipUnless(shutil.which('node'), 'Node.js required for actual browser renderer test')
    def test_picker_renders_shared_atlas_with_search_filters_and_selection(self):
        js = ROOT / 'system/control-center/static/real-estate.js'
        code = r'''
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const elements = Object.create(null);
const $ = id => elements[id] ?? (elements[id] = {innerHTML:'',value:'',hidden:true,addEventListener(){}});
const esc = value => String(value ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
const ctx = vm.createContext({$, esc, window:{},localStorage:{getItem(){return null;},setItem(){}},request(){},toast(){}});
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), ctx);
vm.runInContext(`realEstateState.data={textureReferences:[
  {group:'atlas',reference:'atlas:5',label:'house_level4_01',filename:'house_level4_01_4096x4096_atlas.png',
   path:'assets/source/texture-atlases/house_level4_01/4096x4096/house_level4_01_4096x4096_atlas.png',assetId:'92116826074029'},
  {group:'atlas',reference:'atlas:4',label:'restoration_01',filename:'restoration_01_2048x2048_atlas.png',assetId:'138456659862372'},
  {group:'estate',reference:'estate:house_level2_01:house',label:'house_level2_01 / house',filename:'house.png',assetId:'88003'},
  {group:'location',reference:'location:stone_fence_01',category:'fence',categoryLabel:'Fences',
   label:'Stone fence',filename:'stone.png',assetId:'88004'}]};
 realEstateState.textureRefs.door='atlas:5';
 realEstateState.reuseFilters.door={category:'',query:''};`,ctx);
let html = vm.runInContext('realEstateReuseOptions("door")', ctx);
assert.match(html, /Shared Atlas Registry · published/);
assert.match(html, /<option value="atlas:5">house_level4_01 · house_level4_01_4096x4096_atlas.png · 92116826074029<\/option>/);
assert.match(html, /<option value="atlas:4">restoration_01/);
assert.match(html, /Real Estate · registered/);
assert.match(html, /Location Assets · Fences/);
assert.match(html, /<option value="mesh:house">/);
vm.runInContext('realEstateState.reuseFilters.door.query="92116826074029"',ctx);
html = vm.runInContext('realEstateReuseOptions("door")',ctx);
assert.match(html, /<option value="atlas:5">/);
assert.doesNotMatch(html, /atlas:4/);
assert.doesNotMatch(html, /estate:house_level2_01/);
vm.runInContext('realEstateState.reuseFilters.door={category:"fence",query:"no-match"}',ctx);
html = vm.runInContext('realEstateReuseOptions("door")',ctx);
assert.match(html, /<option value="atlas:5">/); // active reference is preserved
assert.doesNotMatch(html, /<option value="atlas:4">/);
vm.runInContext('realEstateUpdateReuseOptions("door")',ctx);
assert.equal($('real-estate-reference-door').value,'atlas:5');
// The Location category selection is not a global atlas filter.
vm.runInContext('realEstateState.reuseFilters.door={category:"fence",query:"house_level4_01"}',ctx);
html = vm.runInContext('realEstateReuseOptions("door")',ctx);
assert.match(html, /<option value="atlas:5">/);
// The selected value is unchanged by changing how the dropdown is displayed.
assert.equal(vm.runInContext('realEstateState.textureRefs.door',ctx),'atlas:5');
'''
        result = subprocess.run([shutil.which('node'), '-e', code, str(js)],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)


if __name__ == '__main__':
    import unittest
    unittest.main()
