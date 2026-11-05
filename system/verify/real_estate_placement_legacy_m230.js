'use strict';
// Executable DOM-level regression: legacy rows and Place all must be enabled.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname,'../control-center/static/real-estate-placement.js'),'utf8');
const elements = new Map();
function element(id) {
  if (!elements.has(id)) elements.set(id, {
    innerHTML:'',textContent:'',disabled:false,value:'',
    addEventListener(){}, onclick:null, onchange:null,
  });
  return elements.get(id);
}
const context=vm.createContext({
  $:element, realEstateRows:()=>[{slug:'house_level3_01'},{slug:'house_level1_01'}],
  esc:s=>String(s), localStorage:{getItem:()=>null,setItem(){}},
  request:async()=>({}),toast(){},console,
});
vm.runInContext(source,context,{filename:'real-estate-placement.js'});
const old=Array.from({length:39},(_,i)=>({
  plotIndex:i+1,houseSlug:'house_level3_01',houseAnchorLocalCFrame:null,
  worldCFrame:[0,0,0,1,0,0,0,1,0,0,0,1],scale:1,revision:1,anchored:true,
}));
vm.runInContext('realEstatePlacementState.house="house_level3_01"',context);
context.bindings=old;
vm.runInContext('realEstatePlacementState.data={items:bindings};game1RealEstatePlacementRender()',context);
assert.equal(element('re-placement-place-all').disabled,false,'Place all must be enabled for legacy house');
assert.equal((element('re-placement-rows').innerHTML.match(/data-placement-action="place"/g)||[]).length,39);
assert.equal((element('re-placement-rows').innerHTML.match(/Legacy Model pivot/g)||[]).length,39);
assert.doesNotMatch(element('re-placement-rows').innerHTML,/title="Place using original Model pivot \(legacy binding\)" disabled/);
const invalid={...old[0],houseAnchorLocalCFrame:[1,2]};
context.bindings=[invalid];
vm.runInContext('realEstatePlacementState.data={items:bindings};game1RealEstatePlacementRender()',context);
assert.equal(element('re-placement-place-all').disabled,true,'invalid anchor must remain blocked');
const exact={...old[0],houseAnchorLocalCFrame:[0,0,0,1,0,0,0,1,0,0,0,1]};
context.bindings=[exact];
vm.runInContext('realEstatePlacementState.data={items:bindings};game1RealEstatePlacementRender()',context);
assert.equal(element('re-placement-place-all').disabled,false,'calibrated house must remain enabled');
console.log('M230 UI legacy / calibrated / corrupted binding checks: OK');
