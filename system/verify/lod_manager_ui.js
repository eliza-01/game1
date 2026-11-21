'use strict';
// Run: node system/verify/lod_manager_ui.js; UI smoke test without a browser/network.
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');
const html = fs.readFileSync('system/control-center/static/index.html', 'utf8');
for (const id of ['nav-lod-manager', 'lod-manager-view', 'lod-scan', 'lod-snapshot',
                  'lod-rows', 'lod-revisions', 'lod-prepare', 'lod-build-execute',
                  'lod-build-preview', 'lod-source-path', 'lod-search', 'lod-filter',
                  'lod-settings-section', 'lod-workspace-target-radius', 'lod-distance-hide',
                  'lod-enable-ready', 'lod-save-settings', 'lod-copy-workspace', 'lod-preset-default']) {
  assert(html.includes(`id="${id}"`), `missing UI element ${id}`);
}
assert(html.includes('lod-prepare" type="button" disabled'), 'unsafe Prepare button');
const elements = new Map();
const get = id => {
  if (!elements.has(id)) elements.set(id, {innerHTML:'', textContent:'', disabled:false, value:'',
    addEventListener(type, handler) {this[`on_${type}`] = handler;},
    setAttribute(name,value) {this[name]=value;}});
  return elements.get(id);
};
const response = {
  snapshot:{revisionId:12, recordedUtc:1784160000, placeId:99, fingerprint:'abc123',
    freshness:'NOT_LIVE_VERIFIED', catalogMatches:true,warnings:[]},
  summary:{placements:52,typesWithPlacements:1,registeredTypes:1,lod1Types:1,
    missingId:0,duplicateId:0,ambiguous:0,noModel:0,collisionReview:0,scanWarnings:0},
  settings:{schemaVersion:1,modes:{stone_fence_02:'lod1'},
    distances:{lod1:120,lod2:260,hide:400,hysteresis:12},
    workspace:{streamingEnabled:true,minRadius:64,targetRadius:1024,modelStreamingBehavior:'Improved',
      streamingIntegrityMode:'PauseOutsideLoadedArea',streamOutBehavior:'Opportunistic'}},
  items:[{streamingEligible:true,streamingMode:'lod1',streamingReason:'',slug:'stone_fence_02',category:'fence',count:52,fullStatus:'PUBLISHED',
    lod1Status:'PUBLISHED',lod1ModelId:'91896785734146',lod2Status:'NOT_SUPPORTED',
    indicator:'yellow',issues:{missingId:0},recognizedByCatalog:true}],
  revisions:[{id:12,recordedUtc:1784160000,placeId:99,total:52}],
  build:{enabled:false,canPreflight:false, sourceFile:'place/game1_runtime_source.rbxlx'}
};
let preparePayload=null;
const clipboard = {value:'',writeText:async value => {clipboard.value=value}};
const ctx = {document:{getElementById:get},window:{},navigator:{clipboard},request:async (path,opts)=> {
  if (path === '/api/lod-manager/settings') return {...response,settings:{...response.settings,...JSON.parse(opts.body)}};
  if (path === '/api/lod-manager/scan') return {scan:{revisionId:13,unchanged:false,incomplete:false},overview:{...response,
    build:{...response.build,canPreflight:true},
    snapshot:{...response.snapshot,revisionId:13,freshness:'SCANNED_THIS_SESSION'}}};
  if (path === '/api/lod-manager/preflight') return {token:'token1',snapshotRevision:13,eligible:52,
    counts:{stone_fence_02:52}, protectedNotModified:4, sourceSha256:'a'.repeat(64),
    distances:response.settings.distances,workspace:response.settings.workspace};
  if (path === '/api/lod-manager/prepare') {preparePayload=JSON.parse(opts.body);return {backupPath:'backup',runtimePath:'runtime',
    manifestPath:'manifest',reportPath:'report',removedVisualMeshParts:52,publishAllowed:false};}
  return response;
}};
vm.runInNewContext(fs.readFileSync('system/control-center/static/lod-manager.js','utf8'),ctx);
(async()=>{
  await ctx.window.game1LodManagerLoad();
  assert(get('lod-rows').innerHTML.includes('stone_fence_02'));
  assert(get('lod-rows').innerHTML.includes('52'));
  assert(get('lod-rows').innerHTML.includes('91896785734146'));
  assert(get('lod-rows').innerHTML.includes('FULL / LOD1'));
  assert.strictEqual(get('lod-workspace-target-radius').value,'1024');
  await get('lod-scan').on_click();
  assert(get('lod-status').textContent.includes('#13'));
  assert.strictEqual(get('lod-prepare').disabled, false);
  await get('lod-prepare').on_click();
  assert(get('lod-build-preview').textContent.includes('52'));
  assert(!html.includes('id="lod-build-confirm"'));
  assert(html.includes('lm-backup-reminder'));
  assert.strictEqual(get('lod-build-execute').disabled,false);
  await get('lod-build-execute').on_click();
  assert(get('lod-build-status').textContent.includes('ЗАБЛОКИРОВАНА'));
  assert(get('lod-build-preview').textContent.includes('runtime'));
  assert.deepStrictEqual(preparePayload,{token:'token1'},'prepare sends token only');
  await get('lod-copy-workspace').on_click();
  assert(clipboard.value.includes('StreamingTargetRadius=1024'));
  assert(clipboard.value.includes('ModelStreamingBehavior.Improved'));
  await get('lod-preset-default').on_click();
  assert(get('lod-settings-status').textContent.includes('Пресет'));
  await get('lod-disable-all').on_click();
  await new Promise(resolve => setImmediate(resolve));
  assert(get('lod-rows').innerHTML.includes('Off · Workspace'));
  assert(get('lod-settings-status').textContent.includes('Сохранено'));

  console.log('LOD Manager UI smoke: OK');
})().catch(error=>{console.error(error);process.exitCode=1;});
