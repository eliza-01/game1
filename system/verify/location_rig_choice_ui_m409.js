/* M409 · Real yes/no/cancel popup and bounded transport; no Roblox Studio. */
'use strict';
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const src=fs.readFileSync(path.join(root,'system/control-center/static/location-asset-workflow.js'),'utf8');
const needle='  return Object.freeze({open,close,render,startScan});';
assert.ok(src.includes(needle));
class E {
  constructor(tag,all){this.tag=tag;this.children=[];this.handlers={};this.style={};this.value='';this.textContent='';this.open=false;all.push(this)}
  append(...nodes){this.children.push(...nodes)}
  appendChild(node){this.append(node)}
  addEventListener(type,fn){this.handlers[type]=fn}
  showModal(){this.open=true}
  close(){this.open=false}
  remove(){this.removed=true}
  click(){this.handlers.click?.()}
}
const elements=[];
const document={createElement:tag=>new E(tag,elements),body:{appendChild:()=>{}},getElementById:()=>null};
const window={game1ConsumerAtlasEditor:{newState:()=>({})},game1AssetWorkflowDialog:{}};
const context={document,window};vm.createContext(context);
vm.runInContext(src.replace(needle,
  '  window.__m409={askHistoricalRigChoices};\n'+needle),context);
async function test(){
  const ask=context.window.__m409.askHistoricalRigChoices;
  const old=[{key:'p11',modelName:'lantern_01',modelPath:'Workspace.Lights.lantern_01'},
    {key:'p12',modelName:'torch_01',modelPath:'Workspace.Lights.torch_01'}];
  let p=ask(old);
  let selects=elements.filter(e=>e.tag==='select');
  assert.equal(selects.length,2);
  selects[0].value='static';selects[1].value='rig';
  elements.find(e=>e.textContent==='Продолжить Sync').click();
  let decision=await p;
  assert.equal(decision.p11,'static');assert.equal(decision.p12,'rig');
  assert.equal(elements.find(e=>e.tag==='dialog').removed,true);
  elements.length=0;
  p=ask([old[0]]);
  elements.find(e=>e.textContent==='Отмена').click();
  assert.equal(await p,null);
  elements.length=0;
  p=ask([old[0]]);
  elements.find(e=>e.tag==='dialog').handlers.cancel({preventDefault:()=>{}});
  assert.equal(await p,null);
  // Transport has explicit, bounded entries; a direct caller cannot forge a key.
  const out=[];
  const shared={window:{},request:async (_url,options)=>{out.push(JSON.parse(options.body));
    return {studio:{targetSlug:'lantern_01',replacedModels:0}};}};
  vm.createContext(shared);
  vm.runInContext(fs.readFileSync(path.join(root,'system/control-center/static/studio-sync.js'),'utf8'),shared);
  await shared.window.game1StudioSync.replaceLocation('lantern_01','a'.repeat(32),['p11'],{p11:'static'});
  assert.equal(out[0].rigChoices.p11,'static');
  assert.throws(()=>shared.window.game1StudioSync.replaceLocation('lantern_01','a'.repeat(32),['p11'],{p33:'static'}));
  assert.throws(()=>shared.window.game1StudioSync.replaceLocation('lantern_01','a'.repeat(32),['p11'],{p11:'unverified'}));
  console.log('M409 · popup yes/no/cancel and scoped Studio transport OK');
}
test().catch(error=>{console.error(error);process.exitCode=1});
