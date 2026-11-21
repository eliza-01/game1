/* M404: real Place Registry UI flow for repeated IDs and identical hierarchy names. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.resolve(__dirname,'../control-center/static/place-registry.js'),'utf8');
const elements=new Map();
function el(id){
  if(!elements.has(id)) elements.set(id,{id,innerHTML:'',textContent:'',disabled:false,
    checked:false,dataset:{},handlers:{},
    addEventListener(name,callback){this.handlers[name]=callback},
    querySelectorAll(){return[]},replaceChildren(){this.innerHTML=''}});
  return elements.get(id);
}
let repaired=false;const calls=[];
const uid='487214ff-b21e-4ca1-8231-27b9362505f7';
function duplicate(key,x){return {key,slug:'ground_torch_01',name:'ground_torch_01__487214ff',
  path:'Workspace.Places.Ladder.ground_torch_01__487214ff',placementId:uid,canRepair:true,
  canSync:false,duplicateId:true,needsStructure:true,ambiguous:false,issues:[],
  transform:{position:[x,-46.55,-312.98]}}}
const rows=[duplicate('p33',398.41),duplicate('p34',417.90)];
function scan(){return {studio:{placements:repaired?[
    {...rows[0],placementId:'new-unique-guid',name:'ground_torch_01__new',canRepair:false,
     canSync:true,duplicateId:false,needsStructure:false,needsPhysics:true},
    {...rows[1],canRepair:false,canSync:true,duplicateId:false,needsStructure:false,needsPhysics:true}
  ]:rows,scanToken:'12345678-1234-1234-1234-123456789012',
  revision:{revisionId:repaired?216:215,unchanged:false},warnings:[],incomplete:false,
  summary:{placements:2,duplicateIds:repaired?0:2,structure:repaired?0:2,ambiguous:0}}}}
const context={document:{hidden:false,getElementById:el},window:{scrollX:0,scrollY:0,scrollTo(){}},
  state:{view:'place-registry'},localStorage:{getItem:()=>null,setItem(){}},
  setInterval(){},requestAnimationFrame(fn){fn()},confirm(){return true},
  request:async(url,options)=>{
    if(url.endsWith('/actions'))return {actions:[]};
    if(url.includes('/revisions'))return {revisions:[]};
    const payload=JSON.parse(options.body);calls.push(payload);
    if(payload.phase==='scan')return scan();
    if(payload.phase==='repair')repaired=true;
    return {studio:{changed:1,skipped:[],note:'Place repaired'}};
  }};
vm.createContext(context);vm.runInContext(source,context);
const button=(phase,key)=>({dataset:{prAction:phase,key},
  closest(selector){assert.equal(selector,'button[data-pr-action]');return this}});
(async()=>{
  await el('pr-scan').onclick();
  let html=el('pr-groups').innerHTML;
  assert.match(html,/Position 398\.41, -46\.55, -312\.98/);
  assert.match(html,/Position 417\.90, -46\.55, -312\.98/);
  el('pr-groups').handlers.click({target:button('repair','p33')});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(calls[1].phase,'repair');
  assert.deepEqual(calls[1].keys,['p33']);
  assert.equal(calls[2].phase,'scan');
  html=el('pr-groups').innerHTML;
  assert.match(html,/Sync group \(2\)/);
  assert.match(html,/Repair group \(0\)/);
  el('pr-groups').handlers.click({target:button('sync','p33')});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(calls[3].phase,'sync');
  assert.deepEqual(calls[3].keys,['p33']);
  assert.equal(calls[4].phase,'scan');
  console.log('OK M404: duplicate markers distinguish positions; single Repair -> Scan -> Sync');
})().catch(e=>{console.error(e);process.exitCode=1});
