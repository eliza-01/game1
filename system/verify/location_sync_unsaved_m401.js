/* M401 · M400 Model appearance draft blocks Studio Sync, clean Sync All works. */
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const root=path.resolve(__dirname,'..','..');
const source=fs.readFileSync(path.join(root,'system/control-center/static/location-asset-workflow.js'),'utf8');
const marker='  return Object.freeze({open,close,render,startScan});';
assert.ok(source.includes(marker));
const instrumented=source.replace(marker,
  '  window.__m401={state,syncAll,syncSelected,syncPainter,hasUnsavedModelChanges};\n'+marker).replace('};\n'+marker,'};\n'+marker);
const item={slug:'lantern_01',appearanceMode:'material_atlas',visualMaterial:'Plastic',
  visualColor:'#FFFFFF',meshOptions:{},model_asset_id:'123',texture_asset_id:'456',
  bindingRevision:2,alphaEnabled:false};
let confirmations=0;
const ctx={window:{game1ConsumerAtlasEditor:{newState:()=>({})},game1AssetWorkflowDialog:{},
  game1LocationSyncGrouping:{models:()=>[]},confirm:()=>{confirmations++;return false;}},
  decoAssetRow:()=>item,document:{getElementById:()=>null},esc:String};
vm.createContext(ctx);
vm.runInContext(instrumented,ctx,{filename:'location-asset-workflow.js'});
const w=ctx.window.__m401;
assert.ok(w);
const state=w.state;
state.slug='lantern_01';
const originalSig=JSON.stringify(['material_atlas','Plastic','#FFFFFF',{}]);
state.scan={modelId:'123',atlasId:'456',revision:2,alphaEnabled:false,
  appearanceSignature:originalSig,studio:{scanToken:'token',parts:[{key:'p1',managed:true,
    needsTexture:true,instanceId:'placement'}]}};
async function main(){
  state.modelAppearanceDraft={appearanceMode:'material'};
  assert.equal(w.hasUnsavedModelChanges(),true);
  await w.syncAll();
  assert.equal(state.error,true);
  assert.match(state.result,/Model · FBX/);
  assert.equal(confirmations,0);
  await w.syncSelected(['p1']);
  assert.equal(confirmations,0);
  await w.syncPainter([]);
  assert.equal(confirmations,0);
  state.modelAppearanceDraft=null;
  state.physicsDirty=true;
  await w.syncAll();
  assert.equal(confirmations,0);
  state.physicsDirty=false;
  state.pendingModel='new.fbx';
  await w.syncAll();
  assert.equal(confirmations,0);
  state.pendingModel='';
  assert.equal(w.hasUnsavedModelChanges(),false);
  // The saved appearance is current; confirm prompt proves Sync All reached
  // the real selected MeshPart path, without the M400 ReferenceError.
  await w.syncAll();
  assert.equal(confirmations,1);
  assert.match(state.result,/Sync отменён/);
  // Metadata-only edits in Identity must not block Studio Appearance Sync.
  state.identityDraft={nameEn:'Renamed',slug:'lantern_01'};
  await w.syncAll();
  assert.equal(confirmations,2);
  console.log('M401 · Sync All and individual/painter unsaved guards OK');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
