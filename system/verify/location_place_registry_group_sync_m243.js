/* M243 · real client handler contract with a DOM-light Studio response stub. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const src = fs.readFileSync(path.resolve(__dirname, '../control-center/static/place-registry.js'),'utf8');
const elements = new Map();
function element(id) {
  if (!elements.has(id)) elements.set(id, {
    id, innerHTML:'', textContent:'', checked:id==='pr-backup', dataset:{}, disabled:false,
    handlers:{}, addEventListener(name,fn){ this.handlers[name]=fn; },
    querySelectorAll(){return [];}, replaceChildren(){this.innerHTML='';},
  });
  return elements.get(id);
}
const phases=[], confirmations=[];
const rows = [
  {key:'p1',slug:'stone_fence',name:'old',canSync:true,needsMesh:true,needsTexture:false},
  {key:'p2',slug:'stone_fence',name:'blocked',canSync:false,needsMesh:true,needsTexture:true},
  {key:'p3',slug:'birch',name:'other',canSync:true,needsMesh:false,needsTexture:true},
  {key:'p4',slug:'stone_fence',name:'repair only',canSync:false,canRepair:true,needsStructure:true},
];
const scans = () => ({studio:{placements:rows,summary:{placements:4,outdatedMesh:2,outdatedTexture:2,
  structure:1,duplicateIds:0,ambiguous:0},scanToken:'12345678-1234-1234-1234-123456789012',
  revision:{revisionId:1,unchanged:true},warnings:[],incomplete:false}});
const context={
  document:{getElementById:element,hidden:false},
  window:{scrollX:0,scrollY:0,scrollTo(){}},
  state:{view:'other'},
  localStorage:{getItem:()=>null,setItem(){}},
  setInterval(){}, requestAnimationFrame(fn){fn()},
  confirm(text){confirmations.push(text);return true},
  request:async (uri,opts) => {
    if(uri.endsWith('/actions'))return {actions:[]};
    if(uri.includes('/revisions'))return {revisions:[]};
    const payload=JSON.parse(opts.body);
    phases.push(payload);
    if(payload.phase==='scan')return scans();
    return {studio:{changed:1,note:'done',skipped:[]}};
  }
};
vm.createContext(context);
vm.runInContext(src,context);
(async()=>{
  await element('pr-scan').onclick();
  const html=element('pr-groups').innerHTML;
  assert.match(html,/data-pr-action="repair-group"/);
  assert.match(html,/data-pr-action="sync-group"/);
  assert.match(html,/Sync group \(1\)/);
  assert.match(html,/Repair group \(1\)/);
  const groupButton={dataset:{prAction:'sync-group',group:'stone_fence'},
    closest(selector){assert.equal(selector,'button[data-pr-action]');return this}};
  element('pr-groups').handlers.click({target:groupButton});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(phases[1].phase,'sync');
  assert.deepEqual(phases[1].keys,['p1']);
  assert.equal(phases[2].phase,'scan');
  assert.equal(confirmations.length,1);
  assert.match(confirmations[0],/stone_fence · 1 размещений/);
  console.log('OK: group sync selects only the active slug and only eligible pending placements');
})().catch(err=>{console.error(err);process.exitCode=1});
