// M413: an uploaded Real Estate rig uses a publication fingerprint, not raw FBX sha.
const fs=require('fs');
const vm=require('vm');
const assert=require('assert');
const path=require('path');
const root=path.resolve(__dirname,'../control-center/static');
const elements=new Map();
let dialog=null;
let published=[];
const row={slug:'house_level5_01',status:'PUBLISHED',meshParts:['walls_outside'],
  rigAssets:{walls_outside:{assetId:'76514050293314',publishedSha256:'fingerprint-1'}},
  rigSourceHashes:{walls_outside:'raw-sha-1'},
  rigPublicationHashes:{walls_outside:'fingerprint-1'},
  publicationCurrent:{model:true},
  meshSources:{walls_outside:{path:'assets/source/real-estate/revised_walls.fbx',sha256:'raw-sha-1'}},
  textures:{walls_outside:{atlasVariantId:0,atlasBindingRevision:0}}};
function createDialog(){return {
  id:'real-estate-mesh-dialog',open:false,innerHTML:'',
  showModal(){this.open=true},close(){this.open=false},
  querySelector(sel){
    if(sel==='[data-mw-close]')return {onclick:null};
    if(this.innerHTML.includes(sel.replace(/[\[\]]/g,'')))return {onclick:null};
    return null;
  },querySelectorAll(){return [];}
}}
const context=vm.createContext({
  document:{getElementById:id=>elements.get(id)||null},
  window:{game1ConsumerAtlasEditor:{newState:()=>({}),render:()=>'',wire:()=>{}},
   game1AssetWorkflowDialog:{ensure:(id)=>{if(!dialog){dialog=createDialog();elements.set(id,dialog)}return dialog;},
     step:(title,description,body,status)=>`${title} ${body} ${status}`,tabs:()=>''}},
  realEstateRows:()=>[row],realEstateState:{data:{publication:{configured:true},atlasCatalog:[]},atlasBusy:false},
  realEstateForm:()=>{},realEstatePublicationBusy:()=>false,
  realEstatePublish:async (scope,slug)=>{published.push({scope,slug});return {job:{status:'queued',scope}}},
  realEstateReplaceMesh:async()=>true, realEstateSync:async()=>({studio:{realEstateStats:{}}}),
  esc:v=>String(v??''),console
});
vm.runInContext(fs.readFileSync(path.join(root,'real-estate-mesh-workflow.js'),'utf8'),context);
const evaluate=source=>vm.runInContext(source,context);
evaluate("realEstateMeshWorkflowOpen('house_level5_01','walls_outside')");
assert.ok(dialog.open);
assert.match(dialog.innerHTML,/Ready/);
assert.doesNotMatch(dialog.innerHTML,/Publish Model first/);
assert.match(dialog.innerHTML,/Independent mesh FBX/);
assert.match(dialog.innerHTML,/data-mw-sync/);
row.status='UPDATE_AVAILABLE';
evaluate('realEstateMeshWorkflowRender()');
assert.match(dialog.innerHTML,/Finish publishing remaining house assets/);
assert.match(dialog.innerHTML,/data-mw-sync disabled/);
row.status='PUBLISHED';
evaluate('realEstateMeshWorkflowRender()');
// Source SHA differs from publication fingerprint by design. Replacing source
// requires a NEW fingerprint, at which point Sync must be locked again.
row.rigPublicationHashes.walls_outside='fingerprint-2';
evaluate('realEstateMeshWorkflowRender()');
assert.match(dialog.innerHTML,/Publish Model first/);
assert.match(dialog.innerHTML,/Publication required/);
// Make sure mesh publish uses its saved scope/slug rather than a currently
// selected different house in the parent editor.
assert.match(fs.readFileSync(path.join(root,'real-estate-mesh-workflow.js'),'utf8'),
 /realEstatePublish\('model:'\+part\)/);
assert.match(fs.readFileSync(path.join(root,'real-estate.js'),'utf8'),
 /saved\?\.meshSources\?\.\[part\]/); // exact persisted source check
console.log('m413 real estate mesh publication ui: ok');
