/* M278: the Library must not turn an unacknowledged atlas revision into a false warning. */
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const path=require('node:path');
const code=fs.readFileSync(path.resolve(__dirname,'../control-center/static/deco-assets.js'),'utf8');
const test=vm.runInNewContext(code+'\n({decoAssetStudioSyncNote,decoAssetState})',{window:{},$:()=>({})});
const item={slug:'ivy_02',model_asset_id:'132393421464750',texture_asset_id:'83232615212572',
  bindingRevision:1,revision:1,alphaEnabled:false,studioSyncStatus:'unverified'};
assert.equal(test.decoAssetStudioSyncNote(item),'');
test.decoAssetState.studioVerifications.ivy_02={
  modelId:item.model_asset_id,atlasId:item.texture_asset_id,bindingRevision:1,
  authoringRevision:1,alphaEnabled:false,verification:'current'};
assert.equal(test.decoAssetStudioSyncNote(item),'');
test.decoAssetState.studioVerifications.ivy_02.verification='pending';
assert.match(test.decoAssetStudioSyncNote(item),/Sync pending/);
for(const update of [{revision:2},{model_asset_id:'123'},{texture_asset_id:'999'},
                     {bindingRevision:2},{alphaEnabled:true}]){
  assert.equal(test.decoAssetStudioSyncNote({...item,...update}), '', 'stale Find proof must not flag');
}
test.decoAssetState.studioVerifications.ivy_02.verification='review_required';
assert.match(test.decoAssetStudioSyncNote(item),/review required/);
console.log('M278 session-scoped Studio evidence badge: OK');
