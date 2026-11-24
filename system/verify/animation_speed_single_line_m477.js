"use strict";
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const root=path.resolve(__dirname,'../control-center/static');
const elements=new Map();
function element(id){
  if(!elements.has(id))elements.set(id,{
    value:'',innerHTML:'',hidden:false,disabled:false,
    querySelectorAll(){return []},querySelector(){return null}
  });
  return elements.get(id);
}
const context={
  window:{game1AnimationSpeedFilters:require(path.join(root,'animation-speed-filters.js'))},
  localStorage:{getItem(){return null},setItem(){}},
  $:element,esc:value=>String(value).replaceAll('&','&amp;').replaceAll('<','&lt;'),
  toast(){},request:async()=>({}),console
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(root,'animation-speed-catalog.js'),'utf8'),context);
vm.runInContext(fs.readFileSync(path.join(root,'animation-speed.js'),'utf8'),context);
vm.runInContext(`animationSpeedState.data={profiles:[],catalog:[{
  assetId:'89877200678956',kind:'character',name:'1hs_run_01',
  subject:'human_female',scope:'weapon',channel:'run'
}],customScaling:[{assetId:'89877200678956',stat:'RunSpeed',unitsPerPercent:5}]};customScalingRender()`,context);
const html=element('custom-scaling-rows').innerHTML;
const clip=html.match(/<div class="custom-scaling-clip">([\s\S]*?)<\/div>/);
assert.ok(clip,'rendered clip metadata should occupy one container');
assert.match(clip[1],/<strong>1hs_run_01<\/strong>/);
assert.match(clip[1],/human_female/);
assert.match(clip[1],/weapon · run/);
assert.match(clip[1],/id 89877200678956/);
assert.ok(!clip[1].includes('<div'), 'no nested metadata block/second line');
const css=fs.readFileSync(path.join(root,'asset-manager.css'),'utf8');
assert.match(css, /\.custom-scaling-table-row \.custom-scaling-clip\{display:flex;flex-flow:row nowrap;/);
assert.match(css, /\.custom-scaling-table\{min-width:1100px\}/);
assert.match(css, /\.custom-scaling-table-row \.custom-scaling-asset-id\{flex:0 0 auto;white-space:nowrap;/);
assert.ok(html.includes('data-custom-stat')&&html.includes('data-custom-units')&&html.includes('data-custom-apply'));
console.log('m477: all animation metadata fits one no-wrap line; scaling controls preserved');
