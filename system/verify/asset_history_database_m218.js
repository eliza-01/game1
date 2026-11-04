// Executable M218 browser/UI contracts; pure fixture, no service/Studio writes.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ROOT = path.resolve(__dirname, '../..');
const ui = fs.readFileSync(path.join(ROOT,'system/control-center/static/asset-audit.js'),'utf8');
const view = fs.readFileSync(path.join(ROOT,'system/control-center/static/index.html'),'utf8');
const nav = fs.readFileSync(path.join(ROOT,'system/control-center/static/character-assets.js'),'utf8');
assert.match(view, /id="nav-database"/);
assert.match(view, /id="database-nav"/);
assert.match(view, /id="nav-asset-audit"/);
assert.match(view, /id="database-view"/);
assert.match(nav, /if\(saved==='asset-audit'\)saved='database'/);

const elements = {};
const el = id => elements[id] ||= {
  value: '', innerHTML: '', textContent: '', hidden: false, disabled: false, onclick: null,
  addEventListener(event, cb) { this[`on_${event}`] = cb; },
  contains(button) { return button.inList === true; },
};
const copied = [], notices = [], urls = [];
const responseQueue = [];
const globals = {
  document: {getElementById: el},
  $: el,
  window: {},
  navigator: {clipboard: {writeText: async value => {copied.push(value);}}},
  request: async url => {urls.push(url); return responseQueue.shift();},
  toast: (...args) => notices.push(args),
  esc: value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),
};
vm.createContext(globals);
vm.runInContext(ui,globals);
const data = [
  {atUtc:'2026-11-04T00:00:00Z', assetDomain:'location_asset', assetKey:'campfire_01', assetType:'studio_reference', eventKind:'studio_sync',
    changes:[{kind:'atlas',oldId:'111',newId:'222',count:2},{kind:'model_reference',oldId:'333',newId:'444',count:2},{kind:'model',oldId:'201',newId:'301',count:2}]},
  {atUtc:'2026-11-04T01:00:00Z', assetDomain:'texture_atlas', assetKey:'9',assetType:'image', eventKind:'publication',
    changes:[{kind:'asset_publication',oldId:'111',newId:'222',count:1}]},
  {atUtc:'2026-11-04T01:00:00Z',assetDomain:'real_estate',assetKey:'house_01', assetSlot:'door', assetType:'model',eventKind:'publication',
    changes:[{kind:'asset_publication',oldId:'',newId:'555',count:1}]},
  {atUtc:'2026-11-04T02:00:00Z',assetDomain:'character',assetKey:'<script>alert(1)</script>',assetType:'model',eventKind:'publication',
    changes:[{kind:'asset_publication',oldId:'777',newId:'777',count:1}]},
];
async function main() {
  responseQueue.push({events:data,nextCursor:71});
  await globals.window.game1AssetAuditLoad();
  assert.match(urls[0], /^\/api\/asset-replacements\?domain=&key=&limit=200$/);
  assert.match(el('asset-audit-rows').innerHTML,/campfire_01/);
  assert.match(el('asset-audit-rows').innerHTML,/Atlas/);
  assert.match(el('asset-audit-rows').innerHTML,/Model/);
  assert.match(el('asset-audit-rows').innerHTML, /data-copy="301"/);
  assert.match(el('asset-audit-rows').innerHTML,/Shared atlas · variant 9/);
  assert.doesNotMatch(el('asset-audit-rows').innerHTML,/<script>alert/);
  assert.match(el('asset-audit-rows').innerHTML, /data-copy="campfire_01"/);
  assert.match(el('asset-audit-rows').innerHTML, /data-copy="111"/);
  assert.match(el('asset-audit-rows').innerHTML, /data-copy="222"/);
  assert.match(el('asset-audit-rows').innerHTML, /Model ID reference only/);
  assert.match(el('asset-audit-rows').innerHTML, /same ID · content revision/);
  assert.equal(el('asset-audit-more').hidden, false);
  assert.match(el('asset-audit-rows').innerHTML, /title="Previous ID not recorded"/);
  assert.equal((el('asset-audit-rows').innerHTML.match(/class="database-history-row"/g)||[]).length,6);
  // Both ID and slug copy ONLY the clicked value; no automatic clipboard writes.
  assert.equal(copied.length,0);
  const click = (value, inList = true) => el('asset-audit-rows').on_click({target:{closest: () => ({dataset:{copy:value},inList})}});
  click('campfire_01');
  click('222');
  click('wrong', false);
  await new Promise(resolve=>setImmediate(resolve));
  assert.deepEqual(copied,['campfire_01','222']);
  // Atlas filter uses loaded events only; pagination retains underlying events.
  el('asset-audit-type').value='Atlas';
  el('asset-audit-type').onchange();
  assert.equal((el('asset-audit-rows').innerHTML.match(/class="database-history-row"/g)||[]).length,2);
  responseQueue.push({events:[{...data[0],changes:[{kind:'atlas',oldId:'222',newId:'333',count:1}]}],nextCursor:null});
  await globals.assetAuditLoad(false);
  assert.match(urls[1], /&before=71$/);
  assert.equal((el('asset-audit-rows').innerHTML.match(/class="database-history-row"/g)||[]).length,3);
  assert.equal(el('asset-audit-more').hidden,true);
  // HTTP outage is surfaced; no write request or fake empty history.
  globals.request=async()=>{throw Error('mysql unavailable');};
  await globals.assetAuditLoad(true);
  assert.match(el('asset-audit-status').textContent, /mysql unavailable/);
  assert.ok(notices.some(row=>row[1]===true));
  console.log('M218 asset history UI: 21 checks OK');
}
main().catch(error=>{console.error(error);process.exitCode=1});
