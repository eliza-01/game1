/* M238: executable DOM-light checks of Select vs Sync and scroll restoration. */
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const path=require('node:path');
const root=path.resolve(__dirname,'../control-center/static');
const row={slug:'christmas_tree',name_en:'Christmas Tree',category:'tree',status:'PUBLISHED',
  model_asset_id:'136703637428538',model_sha256:'x',model_published_sha256:'x',
  texture_asset_id:'116267630909794',bindingRevision:2,revision:1,model_path:'tree.fbx'};
const part=(key,name,managed,meshCurrent,textureApplicable,textureCurrent)=>({key,name,
  path:'Workspace.Plots.01.'+name,modelPath:managed?'Workspace.Plots.01.Managed':'Workspace.Plots.01.Legacy',
  modelName:managed?'Managed':'Legacy',isCollider:name==='col_mesh',instanceId:managed?'tree1':'',
  meshId:meshCurrent?'108917743354925':'78750137914383',
  textureId:textureApplicable?(textureCurrent?'116267630909794':'130407188742566'):'',
  colorMapId:'',hasSurface:false,textureApplicable,managed,meshCurrent,textureCurrent,
  attachable:!managed,historicalModelId:!managed?'135618055671248':'',
  needsMesh:managed&&!meshCurrent,needsTexture:textureApplicable&&!textureCurrent});
const scan={targetSlug:'christmas_tree',scanToken:'1'.repeat(32),
  foundMeshParts:3,managedMeshParts:2,unmanagedMeshParts:1,managedModels:1,
  expectedMeshIds:['108917743354925','136766989683296'],texturePending:1,
  meshPending:0,geometryPending:0,mode:'texture',inventory:[],parts:[
    part('p1','christmas_tree',false,false,true,false),
    part('p2','col_mesh',true,true,false,true),
    part('p3','visual',true,true,true,false)]};
const scroll={body:0,list:0};
const elements={};
const dialog={open:false,_html:'',
  showModal(){this.open=true;},close(){this.open=false;},
  get innerHTML(){return this._html;},
  set innerHTML(s){this._html=s;scroll.body=0;scroll.list=0;},
  querySelector(name){
    if(name==='.real-estate-mesh-dialog-body')return {get scrollTop(){return scroll.body;},set scrollTop(n){scroll.body=n;}};
    if(name==='.la-sync-list')return this.innerHTML.includes('la-sync-list')?{
      get scrollTop(){return scroll.list;},set scrollTop(n){scroll.list=n;}}:null;
    if(name==='.la-sync-controls details')return null;
    return {onclick:null};
  },querySelectorAll(){return []}
};
const ctx={window:{},document:{getElementById:()=>dialog},
  esc:s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;'),
  decoAssetRow:()=>row,decoAssetState:{data:{publication:{configured:true},
    options:{categories:[]},atlases:[]},atlasBusy:false},
  decoAssetShowSyncHistory:async()=>{},decoAssetLoad:async()=>{},
  toast:()=>{},request:async()=>{},console,Map,Set};
ctx.window.game1AssetWorkflowDialog={ensure:()=>dialog,
  step:(title,description,content)=>`<section>${title}${description}${content}</section>`,
  tabs:()=>'TABS'};
ctx.window.game1ConsumerAtlasEditor={newState:()=>({busy:false}),render:()=>'',wire:()=>{}};
ctx.window.game1MeshAuthoring={seeded:()=>({}),inspectionView:()=>'',wire:()=>{}};
ctx.window.game1StudioSync={scanLocation:async()=>({studio:scan}),
  selectLocation:async(_,__,partKeys)=>({studio:{selectedCount:partKeys.length,selectedPath:''}}),
  replaceLocation:async()=>({studio:{fullySynced:false}}),locationSummary:()=>''};
ctx.window.confirm=()=>true;
vm.runInNewContext(fs.readFileSync(path.join(root,'location-publication-state.js'),'utf8'),ctx);
vm.runInNewContext(fs.readFileSync(path.join(root,'location-asset-workflow.js'),'utf8'),ctx);
(async()=>{
  await ctx.window.game1LocationAssetWorkflow.startScan('christmas_tree');
  assert(dialog.innerHTML.includes('Найдено 3 MeshPart · 2 моделей'));
  assert.equal((dialog.innerHTML.match(/data-la-action="select-studio"/g)||[]).length,2,
    'Studio Select appears for managed AND external Models');
  assert(!dialog.innerHTML.includes('For Sync'), 'Sync checkbox removed');
  assert(dialog.innerHTML.includes('COL ✓ · 1'));
  assert(!dialog.innerHTML.includes('2. col_mesh'),
    'COL MeshPart must not render as a separate row');
  assert(dialog.innerHTML.includes('Найдено по Mesh ID, без привязки к текущему ассету'));
  assert(dialog.innerHTML.includes('Link historical model'));
  scroll.body=187;scroll.list=245;
  ctx.window.game1LocationAssetWorkflow.render();
  assert.equal(scroll.body,187,'main modal keeps scroll after render');
  assert.equal(scroll.list,245,'MeshPart list keeps scroll after render');
  console.log('M238 Select/Sync separation, collider UI, scroll preservation: OK');
})().catch(error=>{console.error(error);process.exitCode=1;});
