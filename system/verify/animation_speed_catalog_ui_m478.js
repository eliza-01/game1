"use strict";
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '../control-center/static');
const elements = new Map();
function el(id) {
  if (!elements.has(id)) elements.set(id, {value:'',innerHTML:'',hidden:false,
    querySelectorAll(){return []},querySelector(){return null}});
  return elements.get(id);
}
const ctx={window:{game1AnimationSpeedFilters:require(path.join(root,'animation-speed-filters.js'))},
  localStorage:{getItem(){return null},setItem(){}},
  $:el,esc:x=>String(x).replaceAll('&','&amp;').replaceAll('<','&lt;'),
  toast(){},request:async()=>({}),console};
vm.createContext(ctx);
for (const file of ['animation-speed-catalog.js','animation-speed.js'])
  vm.runInContext(fs.readFileSync(path.join(root,file),'utf8'),ctx);
vm.runInContext(`animationSpeedState.data={profiles:[],catalog:[
 {assetId:'89877200678956',kind:'character',name:'1hs_run_01',subject:'human_female',scope:'weapon',weaponSet:'1hs',channel:'run'},
 {assetId:'123456789123',kind:'character',name:'social_laugh_02',subject:'human_common',scope:'social',channel:'laugh',availableFor:['human_male','human_female']}
],customScaling:[{assetId:'89877200678956',stat:'RunSpeed',unitsPerPercent:5}]};customScalingRender()`,ctx);
const html=el('custom-scaling-results').innerHTML;
const rows=[...html.matchAll(/<div class="custom-scaling-catalog-row" role="listitem">/g)];
assert.equal(rows.length,2,'all catalog rows still render');
const female=html.slice(html.indexOf('<strong>1hs_run_01</strong>'));
const common=html.slice(html.indexOf('<strong>social_laugh_02</strong>'));
assert.match(female,/custom-scaling-catalog-subject">human_female/);
assert.match(female,/custom-scaling-catalog-action">weapon · 1hs · run/);
assert.match(female,/custom-scaling-catalog-id">id 89877200678956/);
assert.match(female,/Custom · RunSpeed/);
assert.match(female,/data-custom-pick="89877200678956">Edit/);
assert.match(common,/Male \+ Female/);
assert.match(common,/Default · 100%/);
assert.match(common,/data-custom-pick="123456789123">Configure/);
assert.ok(!html.includes('<small>'),'catalog metadata is not rendered as tiny muted footnote');
const css=fs.readFileSync(path.join(root,'asset-manager.css'),'utf8');
assert.match(css, /#custom-scaling-results \.custom-scaling-clip\{\s*display:flex;flex-flow:row nowrap;/);
assert.match(css, /min-width:990px/);
assert.match(css, /custom-scaling-catalog-status\.active/);
assert.match(css, /custom-scaling-catalog-row>button/);
const index=fs.readFileSync(path.join(root,'index.html'),'utf8');
assert.match(index,/asset-manager\.css\?v=478/);
assert.match(index,/animation-speed\.js\?v=478/);
assert.ok(el('custom-scaling-rows').innerHTML.includes('data-custom-stat'), 'custom override editing is retained');
console.log('m478: readable one-line catalog, states, actions, cache-busting and overrides verified');
