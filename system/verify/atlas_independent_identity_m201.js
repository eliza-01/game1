'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const root=path.resolve(__dirname,'../control-center/static');
const identity=require(path.join(root,'atlas-identity.js'));
assert.deepEqual(identity.describe({filename:'structures_01_2048x1024_atlas.png'}),{
 key:'structures_01',name:'structures',variant:'01',resolution:'2048×1024',filename:'structures_01_2048x1024_atlas.png'});
assert.equal(identity.describe({filename:'wall_torch_01.jpg'}).key,'wall_torch_01');
assert.equal(identity.describe({filename:'restoration_01_2048x2048_atlas.png'}).key,'restoration_01');
assert.equal(identity.describe({filename:'wooden_post_kit.png'}).variant,'');
assert.equal(identity.describe({filename:'old_01_512x512_atlas.png',atlasKey:'actual_02'}).key,'actual_02');

const ctx=vm.createContext({window:{},$(){return {innerHTML:'',value:'',addEventListener(){}}},
  esc:v=>String(v??''),localStorage:{getItem(){return null},setItem(){}},request(){},toast(){}});
vm.runInContext(fs.readFileSync(path.join(root,'atlas-identity.js'),'utf8'),ctx);
vm.runInContext(fs.readFileSync(path.join(root,'real-estate.js'),'utf8'),ctx);
vm.runInContext(`realEstateState.data={textureReferences:[
 {reference:'estate:house_level4_01:restoration',group:'estate',label:'house_level4_01 / restoration',filename:'restoration_01_2048x2048_atlas.png',assetId:'138456659862372'},
 {reference:'location:campfire_01',group:'location',label:'Campfire 01',filename:'restoration_01_2048x2048_atlas.png',assetId:'138456659862372'},
 {reference:'estate:house_level7_01:door',group:'estate',label:'house_level7_01 / door',filename:'structures_01_1024x512_atlas.png',assetId:'999999'}]};
 realEstateState.textureRefs.door='location:campfire_01';`,ctx);
const html=vm.runInContext('realEstateReuseOptions("door")',ctx);
assert.match(html,/<optgroup label="restoration_01">/);
assert.match(html,/<optgroup label="structures_01">/);
assert.doesNotMatch(html,/>house_level4_01|Campfire 01|Real Estate · registered|Location Assets ·/); // legacy references remain opaque option values
assert.equal((html.match(/138456659862372/g)||[]).length,1,'two legacy references to same ID are shown as one atlas');
assert.match(html,/<option value="location:campfire_01">restoration_01 · 2048×2048 · 138456659862372/);
assert.match(html,/<option value="estate:house_level7_01:door">structures_01 · 1024×512 · 999999/);
assert.equal(vm.runInContext('realEstateState.textureRefs.door',ctx),'location:campfire_01');
vm.runInContext('realEstateState.reuseFilters.door={query:"house_level4_01"}',ctx);
assert.doesNotMatch(vm.runInContext('realEstateReuseOptions("door")',ctx),/estate:house_level4_01:restoration/);
vm.runInContext('realEstateState.reuseFilters.door={query:"structures_01"}',ctx);
assert.match(vm.runInContext('realEstateReuseOptions("door")',ctx),/structures_01/);
console.log('M201 shared atlas names, legacy IDs, active references, independent search: passed');
