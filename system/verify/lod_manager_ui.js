'use strict';
// Run: node system/verify/lod_manager_ui.js; UI smoke test without a browser/network.
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');
const html = fs.readFileSync('system/control-center/static/index.html', 'utf8');
for (const id of ['nav-lod-manager', 'lod-manager-view', 'lod-scan', 'lod-snapshot',
                  'lod-rows', 'lod-revisions', 'lod-prepare', 'lod-search', 'lod-filter']) {
  assert(html.includes(`id="${id}"`), `missing UI element ${id}`);
}
assert(html.includes('lod-prepare" type="button" disabled'), 'unsafe Prepare button');
const elements = new Map();
const get = id => {
  if (!elements.has(id)) elements.set(id, {innerHTML:'', textContent:'', disabled:false, value:'',
    addEventListener(type, handler) {this[`on_${type}`] = handler;}});
  return elements.get(id);
};
const response = {
  snapshot:{revisionId:12, recordedUtc:1784160000, placeId:99, fingerprint:'abc123',
    freshness:'NOT_LIVE_VERIFIED', catalogMatches:true,warnings:[]},
  summary:{placements:52,typesWithPlacements:1,registeredTypes:1,lod1Types:1,
    missingId:0,duplicateId:0,ambiguous:0,noModel:0,collisionReview:0,scanWarnings:0},
  items:[{slug:'stone_fence_02',category:'fence',count:52,fullStatus:'PUBLISHED',
    lod1Status:'PUBLISHED',lod1ModelId:'91896785734146',lod2Status:'NOT_SUPPORTED',
    indicator:'yellow',issues:{missingId:0},recognizedByCatalog:true}],
  revisions:[{id:12,recordedUtc:1784160000,placeId:99,total:52}],
  build:{enabled:false,reason:'not implemented'}
};
const ctx = {document:{getElementById:get},window:{},request:async (path,opts)=>
  opts ? {scan:{revisionId:13,unchanged:false,incomplete:false},overview:{...response,
    snapshot:{...response.snapshot,revisionId:13,freshness:'SCANNED_THIS_SESSION'}}} : response};
vm.runInNewContext(fs.readFileSync('system/control-center/static/lod-manager.js','utf8'),ctx);
(async()=>{
  await ctx.window.game1LodManagerLoad();
  assert(get('lod-rows').innerHTML.includes('stone_fence_02'));
  assert(get('lod-rows').innerHTML.includes('52'));
  assert(get('lod-rows').innerHTML.includes('91896785734146'));
  await get('lod-scan').on_click();
  assert(get('lod-status').textContent.includes('#13'));
  assert.strictEqual(get('lod-prepare').on_click, undefined, 'Prepare must have no handler');
  console.log('LOD Manager UI smoke: OK');
})().catch(error=>{console.error(error);process.exitCode=1;});
