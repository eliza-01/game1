/* M239: interactive DOM-light test of per-Model grouping, bulk selection and Sync All. */
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const path=require('node:path');
const root=path.resolve(__dirname,'../control-center/static');
const item={slug:'birch_01',name_en:'Birch 01',category:'tree',status:'PUBLISHED',
  model_asset_id:'127245547696536',model_sha256:'same',model_published_sha256:'same',
  texture_asset_id:'105396243494604',bindingRevision:2,revision:1,model_path:'birch.fbx'};
function part(key,name,instance,modelPath,{collider=false,oldMesh=false,oldTex=false,external=false,attachable=false}={}){
  return {key,name,modelName:modelPath.split('.').pop(),modelPath,
    path:modelPath+'.'+name,instanceId:external?'':instance,
    meshId:oldMesh?'78750137914383':'132288181730621',
    textureId:collider?'':oldTex?'999999999':'105396243494604',colorMapId:'',
    hasSurface:false,textureApplicable:!collider,isCollider:collider,
    managed:!external,attachable,historicalModelId:attachable?'75425552383886':'',
    meshCurrent:!oldMesh,textureCurrent:collider||!oldTex,
    needsMesh:!external&&oldMesh,needsTexture:!collider&&oldTex};
}
function scan(parts){
  const managed=parts.filter(p=>p.managed);
  return {targetSlug:item.slug,scanToken:'a'.repeat(32),
    foundMeshParts:parts.length,managedMeshParts:managed.length,
    unmanagedMeshParts:parts.length-managed.length,managedModels:new Set(managed.map(p=>p.instanceId)).size,
    meshPending:managed.filter(p=>p.needsMesh).length,
    texturePending:managed.filter(p=>p.needsTexture).length,
    geometryPending:new Set(managed.filter(p=>p.needsMesh).map(p=>p.instanceId)).size,
    mode:'texture_mesh',expectedMeshIds:['132288181730621','85459199207468'],
    inventory:[{modelAssetId:item.model_asset_id,meshes:[
      {meshId:'132288181730621',count:1,visualNames:['birch_01']},
      {meshId:'85459199207468',count:1,visualNames:[]}]}],parts};
}
const parts=[
  part('p1','birch_01','one','Workspace.Trees.One',{oldTex:true}),
  part('p2','col_mesh','one','Workspace.Trees.One',{collider:true}),
  part('p3','birch_01','two','Workspace.Trees.Two'),
  part('p4','col_mesh','two','Workspace.Trees.Two',{collider:true}),
  part('p5','old_birch','','Workspace.Old.Birch',{external:true,oldMesh:true,attachable:true}),
  part('p6','birch_01','three','Workspace.Trees.Three',{oldMesh:true}),
];
const calls={select:[],sync:[],scan:0};let report=scan(parts);
const buttons={};const scroll={body:0,list:0};
const dialog={open:false,_html:'',showModal(){this.open=true;},close(){this.open=false;},
  get innerHTML(){return this._html;},set innerHTML(html){this._html=html;scroll.body=0;scroll.list=0;},
  querySelector(selector){
    if(selector==='.real-estate-mesh-dialog-body')return {get scrollTop(){return scroll.body;},set scrollTop(value){scroll.body=value;}};
    if(selector==='.la-sync-list')return {get scrollTop(){return scroll.list;},set scrollTop(value){scroll.list=value;}};
    if(selector==='.la-sync-controls details')return null;
    return {onclick:null};
  },
  querySelectorAll(selector){
    if(selector==='[data-la-action]'){
      const pattern=/data-la-action="([\w-]+)"/g;
      return [...this._html.matchAll(pattern)].map(m=>{const node={dataset:{laAction:m[1]},onclick:null};
        buttons[m[1]]=node;return node;});
    }
    const kinds={'[data-la-action="sync-one"]':'sync-one',
      '[data-la-action="select-studio"]':'select-studio',
      '[data-la-action="attach-historical"]':'attach-historical'};
    if(kinds[selector]){
      const html=this._html;
      return [...html.matchAll(/data-la-model-key="(p\d+)"[^>]*>[\s\S]*?<div class="la-sync-part-actions">([\s\S]*?)<\/div>/g)]
        .filter(match=>match[2].includes(`data-la-action="${kinds[selector]}"`))
        .map(match=>({onclick:null,closest:()=>({dataset:{laModelKey:match[1],laLinkKey:'p5'}})}));
    }
    return [];
  },
};
const context={window:{confirm:()=>true},document:{getElementById:()=>dialog},
  esc:value=>String(value??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;'),
  decoAssetRow:()=>item,
  decoAssetState:{data:{publication:{configured:true},options:{categories:[]},atlases:[]},atlasBusy:false},
  decoAssetShowSyncHistory:async()=>{},decoAssetLoad:async()=>{},
  toast:()=>{},request:async()=>{},Map,Set};
context.window.game1AssetWorkflowDialog={ensure:()=>dialog,
  step:(title,description,content)=>`<section>${title}${description}${content}</section>`,tabs:()=>''};
context.window.game1ConsumerAtlasEditor={newState:()=>({busy:false}),render:()=>'',wire:()=>{}};
context.window.game1MeshAuthoring={seeded:()=>({}),inspectionView:()=>'',wire:()=>{}};
context.window.game1StudioSync={
  scanLocation:async()=>{calls.scan++;return {studio:report};},
  selectLocation:async(_slug,_token,keys)=>{calls.select.push(keys);return {studio:{selectedCount:keys.length}};},
  replaceLocation:async(_slug,_token,keys)=>{calls.sync.push(keys);return {studio:{fullySynced:true}};},
  locationSummary:()=>'',
};
vm.runInNewContext(fs.readFileSync(path.join(root,'location-publication-state.js'),'utf8'),context);
vm.runInNewContext(fs.readFileSync(path.join(root,'location-asset-workflow.js'),'utf8'),context);
(async()=>{
  context.window.game1LocationAssetWorkflow.open('birch_01');
  assert(dialog.innerHTML.includes('Registration details'),'Edit opens Identity');
  assert(dialog.innerHTML.includes('data-la-action="replace-all"'),'Sync All available before Find');
  assert(!dialog.innerHTML.includes('Already up to date'));
  await context.window.game1LocationAssetWorkflow.startScan('birch_01');
  assert(dialog.innerHTML.includes('Найдено 6 MeshPart · 4 моделей'));
  assert.equal((dialog.innerHTML.match(/data-la-model-key="p/g)||[]).length,4);
  assert.equal((dialog.innerHTML.match(/COL ✓ · 1/g)||[]).length,2);
  assert.equal((dialog.innerHTML.match(/⚠ COL-меш не найден/g)||[]).length,2);
  assert.equal((dialog.innerHTML.match(/data-la-action="sync-one"/g)||[]).length,3);
  assert(!dialog.innerHTML.includes('For Sync'));
  await buttons['select-all'].onclick();
  assert.equal(calls.select.length,1,'one Studio bridge selection, not N HTTP commands');
  assert.deepEqual(Array.from(calls.select[0]),['p1','p3','p5','p6'], 'select every model including historical');
  assert.deepEqual(calls.sync,[],'Select does not replace anything');
  scroll.body=123;scroll.list=88;context.window.game1LocationAssetWorkflow.render();
  assert.equal(scroll.body,123);assert.equal(scroll.list,88);
  await buttons['replace-all'].onclick();
  assert.equal(calls.sync.length,1);
  assert.deepEqual(Array.from(calls.sync[0]),['p1','p6'], 'only pending managed MeshParts');
  assert.equal(calls.scan,2,'Sync automatically scans updated Place without closing the list');
  assert(dialog.innerHTML.includes('Найдено 6 MeshPart · 4 моделей'));
  assert(dialog.innerHTML.includes('Список обновлён'));
  context.window.game1StudioSync.replaceLocation=async()=>{throw Error('bridge refused');};
  await buttons['replace-all'].onclick();
  assert(dialog.innerHTML.includes('bridge refused'),'show real bridge failure');
  assert(dialog.innerHTML.includes('Найдено 6 MeshPart · 4 моделей'),'keep report after failed sync');
  assert.equal(calls.scan,3,'re-verify Place even after failed mutation');
  context.window.game1StudioSync.scanLocation=async()=>{throw Error('Scan offline');};
  await buttons['replace-all'].onclick();
  assert(dialog.innerHTML.includes('Найдено 6 MeshPart · 4 моделей'),'report survives failed refresh');
  assert(dialog.innerHTML.includes('Требуется новый Find перед Sync'),'stale data is visibly locked');
  assert.match(dialog.innerHTML,/data-la-action="replace-all" disabled/,'stale report cannot be used for mutation');
  context.window.game1StudioSync.scanLocation=async()=>{calls.scan++;return {studio:report};};
  context.window.game1StudioSync.replaceLocation=async(_slug,_token,keys)=>{calls.sync.push(keys);return {studio:{fullySynced:true}};};
  report=scan(parts.map(p=>({...p,needsMesh:false,needsTexture:false,meshCurrent:true,textureCurrent:true})));
  await context.window.game1LocationAssetWorkflow.startScan('birch_01');
  await buttons['replace-all'].onclick();
  assert.equal(calls.sync.length,1,'already current must not mutate Place');
  assert(dialog.innerHTML.includes('Все размещённые модели актуальны') ||
    dialog.innerHTML.includes('Среди привязанных моделей изменений нет'));
  console.log('M239 grouping, Studio Select All, Sync All, no-op, scroll, COL: OK');
})().catch(error=>{console.error(error);process.exitCode=1;});
