/* M219 executable client contracts: one slug per request, no implicit global sync,
 * duplicate request guard, and shared house / decor transport. */
const fs = require('fs');
const assert = require('assert');
const vm = require('vm');
const path = require('path');
const staticDir = path.resolve(__dirname, '../control-center/static');
const body = fs.readFileSync(path.join(staticDir, 'studio-sync.js'), 'utf8');
const calls = [];
let hold;
let pause = false;
const context = {window: {}, request: async (url, init) => {
  const payload = JSON.parse(init.body);
  calls.push({url, payload, init});
  if (pause) await new Promise(resolve => {hold = resolve;});
  if (url === '/api/location-assets/studio-sync') return {
    studio: {targetSlug: payload.slug, replacedModels: 0, matchedModels: 4,
      parts: 8, modelReferences: 1, pendingGeometry: 2,
      scanToken: '1'.repeat(32), mode: 'texture_mesh',selectedMeshParts:5},
  };
  return {studio: {realEstateStats: {placedSyncVersion: 2}}};
}};
const sandbox = vm.createContext(context);
vm.runInContext(body, sandbox, {filename:'studio-sync.js'});
const sync = context.window.game1StudioSync;
(async () => {
  await assert.rejects(sync.run('location', ''), /slug/);
  await assert.rejects(sync.run('location', 'foo bar'), /slug/);
  assert.throws(()=>sync.run('location', 'oak', {part: 'house'}), /entire asset/);
  assert.throws(()=>sync.run('global', 'oak'), /Unsupported/);
  assert.strictEqual(calls.length, 0);
  const row = await sync.run('location', 'campfire_01');
  assert.strictEqual(calls.length, 1);
  assert.strictEqual(calls[0].url, '/api/location-assets/studio-sync');
  assert.strictEqual(calls[0].payload.slug, 'campfire_01');
  assert.strictEqual(row.studio.matchedModels, 4);
  assert.strictEqual(calls[0].payload.phase, 'scan');
  assert(sync.locationSummary('campfire_01', row.studio).includes('placed instances 4'));
  assert(sync.locationSummary('campfire_01', row.studio).includes('geometry updated'));
  await sync.run('real-estate', 'house_level2_01', {part: 'window_frames_glass'});
  assert.strictEqual(calls[1].url, '/api/real-estate/house_level2_01/sync');
  assert.strictEqual(calls[1].payload.part, 'window_frames_glass');
  pause = true;
  const p = sync.run('location', 'bush_01');
  await assert.rejects(sync.run('location', 'bush_01'), /another command/i);
  await assert.rejects(sync.run('real-estate', 'house_level2_01'), /another command/i);
  hold();
  await p;
  pause = false;
  await sync.run('location', 'bush_01'); // retry works after completion
  assert.strictEqual(calls.length, 4);
  // Browser action receives a row slug, even if another asset is active in the
  // registration form. This caught the misleading pre-M219 selection UX.
  const locationSource = fs.readFileSync(path.join(staticDir, 'deco-assets.js'), 'utf8');
  assert(locationSource.includes('window.game1LocationAssetWorkflow.startScan(row.slug)'));
  assert.strictEqual(calls.at(-1).payload.phase,'scan');
  await sync.replaceLocation('campfire_01','1'.repeat(32),['p1']);
  assert.strictEqual(calls.at(-1).payload.phase,'replace');
  assert.strictEqual(calls.at(-1).payload.scanToken,'1'.repeat(32));
  assert.deepStrictEqual(calls.at(-1).payload.selectedKeys,['p1']);
  console.log('M219 client Studio Sync contracts: OK');
})().catch(error => {console.error(error); process.exitCode = 1;});
