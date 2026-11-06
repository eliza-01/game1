"""M247: Real Estate layout cleanup keeps registration, library and atlas reuse functional."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from unittest import TestCase, skipUnless

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / 'system/control-center/static'


class RealEstateLayoutM247(TestCase):
    def test_ui_removes_duplicate_atlas_library_but_preserves_shared_atlas_navigation(self):
        html = (STATIC / 'index.html').read_text(encoding='utf-8')
        view = html.split('id="real-estate-view"', 1)[1].split('id="locations-view"', 1)[0]
        self.assertNotIn('central atlas registry', view)
        self.assertNotIn('id="real-estate-atlas-rows"', view)
        self.assertNotIn('id="real-estate-atlas-house"', view)
        self.assertIn('id="nav-atlas"', html)
        self.assertIn('id="real-estate-library-rows"', view)
        self.assertIn('<th>house</th><th>source textures</th><th>assets</th><th>actions</th>', view)

    def test_identity_fields_are_stacked_and_library_height_is_2_5_times_original(self):
        html = (STATIC / 'index.html').read_text(encoding='utf-8')
        view = html.split('id="real-estate-view"', 1)[1].split('id="locations-view"', 1)[0]
        self.assertEqual(view.count('class="real-estate-identity-fields"'), 2)
        for name in ('type', 'level', 'variant', 'purchase', 'min-level', 'sale'):
            self.assertIn('id="real-estate-' + name + '"', view)
        css = (STATIC / 'real-estate.css').read_text(encoding='utf-8')
        self.assertRegex(css, r'\.real-estate-identity-fields\s*\{[^}]*grid-template-columns:minmax\(0,1fr\)')
        self.assertRegex(css, r'\.real-estate-library\s*>\s*\.table-wrap\s*\{\s*max-height:1300px')
        self.assertIn('field-sizing:content', css)
        self.assertNotIn('real-estate-atlas-filters', css)

    @skipUnless(shutil.which('node'), 'Node.js required for Real Estate renderer contract')
    def test_house_name_level_and_economy_share_one_cell_without_atlas_library(self):
        code = r'''
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const elements=new Map();
const $=id=>{
  if(!elements.has(id))elements.set(id,{innerHTML:'',textContent:'',hidden:true,value:'',
    addEventListener(){},querySelectorAll(){return []}});
  return elements.get(id);
};
const ctx=vm.createContext({$,esc:v=>String(v??''),window:{},request(){},toast(){},
  localStorage:{getItem(){return null},setItem(){}}});
vm.runInContext(fs.readFileSync('real-estate.js','utf8'),ctx);
vm.runInContext(`realEstateIdentity=()=>{};
realEstateState.data={publication:{configured:true},items:[{
  slug:'house_level5_01',house_level:5,variant:'01',purchase_price:1,
  sale_price:1,min_level:1,meshParts:[],textures:{},rigAssets:{},
  publicationCurrent:{},rigSourceHashes:{},status:'LOCAL_ONLY'}]};
realEstateRender();`,ctx);
const result=$('real-estate-library-rows').innerHTML;
assert.match(result,/<td class="real-estate-house-cell"><b>house_level5_01<\/b>/);
assert.match(result, /level 5 · variant 01/);
assert.match(result, /buy 1 · sell 1/);
assert.match(result, /level required 1/);
assert.equal((result.match(/<td(?: |>| class=)/g)||[]).length,4);
assert.doesNotMatch(result,/real-estate-atlas-rows/);
'''
        result = subprocess.run(['node', '-e', code], cwd=STATIC, capture_output=True,
                                text=True, encoding='utf-8', timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
