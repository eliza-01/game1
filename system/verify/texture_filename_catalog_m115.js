'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '../control-center/static');
function evaluate(script) {
  const elements = new Map();
  const get = (id) => {
    if (!elements.has(id)) elements.set(id, {
      hidden:true, value:'', options:[], innerHTML:'', textContent:'',
      children:[], appendChild(item){this.children.push(item);},
      querySelectorAll(){return [];}, addEventListener(){}
    });
    return elements.get(id);
  };
  const context = vm.createContext({
    $:get, esc:(value)=>String(value??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;'),
    window:{}, localStorage:{getItem(){return null;},setItem(){},removeItem(){}},
    document:{createElement(tag){return {tag,innerHTML:'',value:'',textContent:'',className:'',children:[],appendChild(item){this.children.push(item);},querySelector(selector){return selector === "[data-retry]" ? null : {onclick:null};},querySelectorAll(){return []}};}},
    request(){},toast(){},game1SyncPublicationDescription(){},
  });
  vm.runInContext(fs.readFileSync(path.join(root,script),'utf8'),context,{filename:script});
  return {context, get};
}
{
  const {context, get}=evaluate('real-estate.js');
  vm.runInContext(`realEstateState.data={textureReferences:[
    {reference:'location:granite_wall', group:'location', category:'rock', categoryLabel:'Rocks',
     label:'Granite Wall',slug:'granite_wall',filename:'Custom Atlas 4.PNG', path:'assets/granite_wall.png', assetId:'12345'},
    {reference:'estate:house_level5_01:house',group:'estate',label:'house_level5_01 / house',
     slug:'house_level5_01',filename:'Villa_Atlas.webp',assetId:'55556'}]};
    realEstateState.reuseFilters.house={query:'atlas 4',category:''};`,context);
  let html = vm.runInContext('realEstateReuseOptions("house")',context);
  assert.match(html, /Granite Wall · Custom Atlas 4.PNG · 12345/);
  assert.doesNotMatch(html, /Villa_Atlas/);
  vm.runInContext('realEstateState.reuseFilters.house.query="granite_wall"',context);
  html = vm.runInContext('realEstateReuseOptions("house")',context);
  assert.match(html,/Granite Wall · Custom Atlas 4.PNG · 12345/);
  vm.runInContext('realEstateState.reuseFilters.house.query="villa_atlas"',context);
  html = vm.runInContext('realEstateReuseOptions("house")',context);
  assert.match(html,/house_level5_01 \/ house · Villa_Atlas.webp · 55556/);
  assert.doesNotMatch(html, /Granite Wall/);
  vm.runInContext(`realEstateState.data.items=[{slug:'house_level5_01', house_level:5,variant:'01',
    status:'PUBLISHED', meshParts:['house','door'], textures:{
      house:{path:'assets/house.png',assetId:'88'},door:{path:'assets/door.png',assetId:'99'}},
    rigAssets:{house:{assetId:'66'},door:{assetId:'77'}},publicationCurrent:{model:true,house:true,door:true}}];
    realEstateState.data.publication={configured:true}; realEstateState.selected='house_level5_01';`,context);
  vm.runInContext('realEstateRender()',context);
  const library=get('real-estate-library-rows').innerHTML;
  assert.equal((library.match(/class="real-estate-asset-part"/g)||[]).length,2);
  assert.equal((library.match(/real-estate-asset-model/g)||[]).length,2);
  assert.equal((library.match(/real-estate-asset-image/g)||[]).length,2);
  assert.match(library,/model<\/span><code>66<\/code>/);
  assert.match(library,/image<\/span><code>99<\/code>/);
  html = vm.runInContext('realEstateReuseOptions("door")',context);
  assert.match(html,/this Estate \/ house · house.png · 88/);
}
{
  const {context,get}=evaluate('deco-assets.js');
  vm.runInContext(`decoAssetState.data={items:[
      {slug:'granite_wall',name_en:'Granite Wall',category:'rock',texture_path:'assets/granite_wall.png',texture_filename:'Atlas (Original).png',
       texture_owner_slug:'granite_wall',texture_asset_id:'12345', status:'PUBLISHED'},
      {slug:'prop',name_en:'Prop',category:'rock',texture_owner_slug:'granite_wall',texture_shared:true,
       texture_filename:'Atlas (Original).png',texture_asset_id:'12345',status:'PUBLISHED'}],
      options:{categories:[{id:'rock',label:'Rocks'}]},summary:{registered:2,published:2,changed:0},publication:{configured:false}};
    decoAssetState.libraryCategory='all';`,context);
  vm.runInContext('decoAssetRenderTextureReferences()',context);
  const options=get('location-asset-texture-reference').children;
  assert.equal(options.length,1);
  assert.equal(options[0].label, 'Legacy texture reuse (compatibility only)');
  assert.equal(options[0].children[0].value,'legacy:granite_wall');
  assert.match(options[0].children[0].textContent,/Atlas \(Original\)\.png · 12345/);
  vm.runInContext('decoAssetRender()',context);
  assert.match(get('location-asset-rows').children[0].innerHTML, /Granite Wall<\/b><small>granite_wall<\/small><small class="deco-texture-filename">Atlas \(Original\)\.png/);
}
console.log('M115 browser-side labels, search and house asset grouping: passed');
