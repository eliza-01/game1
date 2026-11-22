"use strict";
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const read=name=>fs.readFileSync('system/control-center/static/'+name,'utf8');
const html=read('index.html');
const ui=read('lod-manager.js');
const mesh=read('real-estate-mesh-workflow.js');
assert(html.includes('id="lod-house-search"'));
assert(html.includes('id="lod-house-filter"'));
assert(!html.includes('<tbody id="lod-house-rows"'), 'house is no longer a dense table');
assert(html.includes('real-estate-mesh-workflow.js?v=423'), 'asset must reload on fresh version');
assert(!ui.includes('choose-real-estate-model'), 'LOD Manager may not pick FBX');
assert(!ui.includes('/lod1-stage') && !ui.includes('/lod1-reuse') && !ui.includes('/lod1-publish'));
assert(mesh.includes("{id:'lod1',label:'LOD1 · FBX'}"));

const row={slug:'house_level5_01',meshParts:['roof'],status:'PUBLISHED',
  partLod1:{roof:{status:'NOT_REGISTERED',revision:0,modelAssetId:''}},
  rigAssets:{roof:{assetId:'10',publishedSha256:'same'}},rigPublicationHashes:{roof:'same'},
  meshSources:{},textures:{roof:{atlasVariantId:0,atlasBindingRevision:0}}};
const urls=[];
const dialog={open:false,innerHTML:'',buttons:{},showModal(){this.open=true},close(){this.open=false},
  querySelector(selector){
    if(selector==='[data-mw-close]')return {onclick:null};
    const name=selector.slice(1,-1);
    if(!this.innerHTML.includes(name))return null;
    if(!this.buttons[name])this.buttons[name]={onclick:null};
    return this.buttons[name];
  },querySelectorAll(){return []}};
let chosen='C:/FBX/house_level5_01_roof_lod1.fbx';
const ctx=vm.createContext({
  document:{getElementById:id=>id==='real-estate-mesh-dialog'?dialog:null},
  window:{game1ConsumerAtlasEditor:{newState:()=>({}),render:()=>'',wire:()=>{}},
    game1AssetWorkflowDialog:{ensure:()=>dialog,step:(_title,_desc,body)=>body,tabs:()=>''},
    game1LodReusePicker:{pick:async()=>({domain:'location',slug:'roof_reuse',revision:2,modelAssetId:'500'}),
      payload:(_choice,revision)=>({expectedRevision:revision,sourceModelAssetId:'500',sourceDomain:'location',sourceSlug:'roof_reuse',sourceRevision:2})}},
  realEstateRows:()=>[row],realEstateForm:()=>{},
  realEstatePublicationBusy:()=>false,realEstateLoad:async()=>{},
  realEstateState:{data:{publication:{configured:true},atlasCatalog:[]},atlasBusy:false},
  esc:value=>String(value??''),
  request:async(url,options)=>{
    urls.push(url);
    if(url==='/api/files/choose-real-estate-model')return {path:chosen};
    const body=JSON.parse(options.body);
    assert.equal(body.expectedRevision,row.partLod1.roof.revision);
    if(url.endsWith('/lod1-stage')){
      assert.equal(body.sourcePath,chosen);
      row.partLod1.roof={status:'STAGED',revision:1,modelAssetId:''};
    }
    if(url.endsWith('/lod1-publish')){
      assert.equal(row.partLod1.roof.status,'STAGED');
      row.partLod1.roof={status:'PUBLISHED',revision:1,modelAssetId:'700'};
    }
    if(url.endsWith('/lod1-reuse')){
      assert.equal(body.sourceModelAssetId,'500');
      row.partLod1.roof={status:'PUBLISHED',revision:2,modelAssetId:'500'};
    }
    return {};
  },console
});
vm.runInContext(mesh,ctx);
const run=source=>vm.runInContext(source,ctx);
const click=async id=>{
  const button=dialog.querySelector('[data-mw-'+id+']');
  assert(button?.onclick,'button '+id+' must have handler');
  await button.onclick();
};
(async()=>{
  run("realEstateMeshWorkflowOpen('house_level5_01','roof','lod1')");
  assert(dialog.open);
  assert(dialog.innerHTML.includes('LOD1 FBX'));
  assert(!dialog.innerHTML.includes('data-mw-sync'), 'FULL Sync should not appear on LOD1 tab');
  chosen='C:/FBX/wrong.fbx';
  await click('lod-choose');
  assert(run('realEstateMeshWorkflow.error'));
  assert.equal(run('realEstateMeshWorkflow.lodSource'),'');
  chosen='C:/FBX/house_level5_01_roof_lod1.fbx';
  await click('lod-choose');
  assert.equal(run('realEstateMeshWorkflow.lodSource'),chosen);
  await click('lod-stage');
  assert.equal(row.partLod1.roof.status,'STAGED');
  assert.equal(run('realEstateMeshWorkflow.lodSource'),'');
  await click('lod-publish');
  assert.equal(row.partLod1.roof.modelAssetId,'700');
  await click('lod-reuse');
  assert.equal(row.partLod1.roof.modelAssetId,'500');
  assert(urls.some(x=>x.endsWith('/lod1-stage')));
  assert(urls.some(x=>x.endsWith('/lod1-publish')));
  assert(urls.some(x=>x.endsWith('/lod1-reuse')));
  assert(!urls.some(x=>x.includes('/api/lod-manager')));
  console.log('M423 Real Estate LOD1 ownership and UI: OK');
})().catch(e=>{console.error(e);process.exitCode=1;});
