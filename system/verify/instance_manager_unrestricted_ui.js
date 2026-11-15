/* M353: frontend protocol smoke test without browser dependencies. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
const source = fs.readFileSync(path.join(root, 'system/control-center/static/location-instance-manager.js'), 'utf8');
const listeners = new Map();
class Option {
  constructor(label, value) { this.label=label; this.textContent=label; this.value=value; }
}
class Element {
  constructor(name) {
    this.name=name;this.disabled=false;this.hidden=false;this.checked=false;
    this.value='';this.innerHTML='';this.textContent='';this.options=[];this.selectedOptions=[];
    this.listeners={};
  }
  addEventListener(event, callback) { this.listeners[event]=callback; }
  replaceChildren(...options) { this.options=[...options]; this.value=options[0]?.value||''; this.innerHTML=''; }
  add(option) {this.options.push(option);}
  get selectedOptions() { return this.options.filter(o => o.value===this.value); }
  set selectedOptions(_v) {}
  dispatch(event, payload) { return this.listeners[event]?.(payload); }
}
const els = new Map();
function get(id){ if (!els.has(id))els.set(id,new Element(id));return els.get(id); }
const token='12345678-1234-1234-1234-123456789abc';
const inspectionToken='abcdef12-3456-7890-abcd-abcdef123456';
const sent=[];
let replacementMade=false;
const responses={
  preview:{count:1, scanToken:token, placements:[{name:'stone fence',path:'Workspace.fence',placementId:token,newPlacementId:token}],
   anchorOptions:[{id:'model',label:'Model'},{id:'geometry',label:'Geometry'}],
   reassignedIds:0, normalizedPivots:0,preservedManualSizes:0,differingVisualAxes:0},
  inspect:{count:1,inspectionToken,collisionParts:1,warnings:1,
   warningDetails:[{index:1,path:'Workspace.fence',partId:'wall',shape:'Wedge',approximate:true,reason:'Approximate Wedge',excessStuds:[1.1,0,0],addedPercent:[21,0,0]}]},
  focus:{count:1,focused:true,index:1,partId:'wall'},
  replace:{count:1,changed:1,reassignedIds:0}
};
const context={
  Option,document:{getElementById:get},window:{},
  confirm:()=>true,
  fetch:async (_url,opts)=>{
    const payload=JSON.parse(opts.body);sent.push(payload);
    if(payload.phase==='replace') {replacementMade=true;assert.equal(payload.approveShear,true);}
    return {ok:true,json:async()=>({studio:responses[payload.phase]})};
  }
};
vm.createContext(context);
vm.runInContext(source,context);
const rows=[{slug:'stone_fence_01',status:'PUBLISHED',model_asset_id:'10'},
 {slug:'stone_fence_02',status:'PUBLISHED',model_asset_id:'20'}];
context.window.game1LocationInstanceRefresh(rows);
get('li-source').value='stone_fence_01';get('li-target').value='stone_fence_02';
(async()=>{
  await get('li-preview').dispatch('click');
  await get('li-inspect').dispatch('click');
  assert.equal(get('li-replace').disabled,true, 'oversized geometry blocked by default');
  assert.match(get('li-collision-warnings').innerHTML, /Показать в Studio/);
  assert.match(get('li-collision-warnings').innerHTML, /ПРИБЛИЖЕНИЕ/);
  assert.match(get('li-collision-warnings').innerHTML, /Wedge/);
  assert.match(get('li-collision-warning-count').textContent,/1/);
  context.window.game1LocationInstanceRefresh([...rows].reverse());
  assert.equal(get('li-inspect').disabled,false,'reordering catalog retains inspection');
  const button={dataset:{liFocusIndex:'1',liFocusPart:'wall'}};
  await get('li-collision-warnings').dispatch('click',{target:{closest:()=>button}});
  await new Promise(r=>setImmediate(r));
  assert.equal(sent.at(-1).phase,'focus');
  assert.equal(sent.at(-1).inspectionToken,inspectionToken);
  assert.equal(get('li-replace').disabled,true);
  get('li-approve-shear').checked=true;
  get('li-approve-shear').dispatch('change');
  assert.equal(get('li-replace').disabled,false);
  await get('li-replace').dispatch('click');
  assert.equal(replacementMade,true);
  console.log('Instance Manager unrestricted UI smoke: OK');
})().catch(e=>{console.error(e);process.exitCode=1});
