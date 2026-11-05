/* M237: executable DOM-light smoke of per-part report and automatic action. */
const fs=require('fs');
const vm=require('vm');
const assert=require('assert');
const path=require('path');
const root=path.resolve(__dirname,'../control-center/static');
const dialog={innerHTML:'',open:false,showModal(){this.open=true;},close(){this.open=false;},
  querySelectorAll(){return [];},querySelector(){return {onclick:null};}};
const row={slug:'christmas_tree',name_en:'Christmas Tree',category:'tree',status:'PUBLISHED',
  model_asset_id:'136703637428538',model_sha256:'x',model_published_sha256:'x',
  texture_asset_id:'116267630909794',bindingRevision:2,revision:1,model_path:'tree.fbx'};
const makeRow=(key,name,managed,meshCurrent,textureCurrent)=>({key,name,
  path:'Workspace.Trees.'+name,modelPath:managed?'Workspace.Trees.tree1':'Workspace.Trees.old',
  modelName:managed?'tree1':'old',isCollider:false,instanceId:managed?'tree1':'',
  meshId:meshCurrent?'108917743354925':'78750137914383',
  textureId:textureCurrent?'116267630909794':'130407188742566',
  colorMapId:'',hasSurface:false,textureApplicable:true,managed,meshCurrent,textureCurrent,
  attachable:false,historicalModelId:'',
  needsMesh:managed&&!meshCurrent,needsTexture:!textureCurrent});
const scan={targetSlug:'christmas_tree',scanToken:'1'.repeat(32),
  foundMeshParts:4,managedMeshParts:3,unmanagedMeshParts:1,managedModels:2,
  expectedMeshIds:['108917743354925','136766989683296'],texturePending:2,
  meshPending:1,geometryPending:1,mode:'texture_mesh',inventory:[],
  parts:[makeRow('p1','fresh',true,true,true),
    makeRow('p2','old_texture',true,true,false),
    makeRow('p3','old_mesh',true,false,false),
    makeRow('p4','external',false,false,false)]};
const calls=[];
const sandbox={window:{},document:{getElementById:()=>dialog},
  esc:s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;'),
  decoAssetRow:()=>row,
  decoAssetState:{data:{publication:{configured:true},options:{categories:[]},atlases:[]},atlasBusy:false},
  decoAssetShowSyncHistory:async()=>{},decoAssetLoad:async()=>{},
  toast:()=>{},request:async()=>{},
  console,Map,Set};
sandbox.window.game1AssetWorkflowDialog={ensure:()=>dialog,
  step:(title,desc,content)=>`<section>${title}${desc}${content}</section>`,
  tabs:()=>'TABS'};
sandbox.window.game1ConsumerAtlasEditor={newState:()=>({busy:false}),
  render:()=>'<div>atlas editor</div>',wire:()=>{}};
sandbox.window.game1MeshAuthoring={seeded:()=>({}),inspectionView:()=>'',wire:()=>{}};
sandbox.window.game1StudioSync={scanLocation:async()=>({studio:scan}),
  replaceLocation:async(_,__,selectedKeys)=>{calls.push(selectedKeys);return {studio:{fullySynced:false}};},
  locationSummary:()=>''};
sandbox.window.confirm=()=>true;
vm.runInNewContext(fs.readFileSync(path.join(root,'location-asset-workflow.js'),'utf8'),sandbox);
(async()=>{
  await sandbox.window.game1LocationAssetWorkflow.startScan('christmas_tree');
  const html=dialog.innerHTML;
  for(const fragment of ['Актуальные Mesh ID','116267630909794','130407188742566',
    'Найдено 4 MeshPart · 2 моделей','Mesh ✓ актуальный','Mesh ✕ устаревший',
    'Texture ✕ устаревший','Select All · Studio','Sync All',
    'Историческая модель без привязки']){
    assert(html.includes(fragment),fragment);
  }
  assert.strictEqual((html.match(/data-la-model-key=/g)||[]).length,2,'Models grouped');
  assert(!html.includes('For Sync'),'no Sync marks remain');
  console.log('M237 per-part renderer: OK');
})().catch(error=>{console.error(error);process.exitCode=1;});
