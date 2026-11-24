'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const core=require('../control-center/static/animation-publish-queue-core.js');
const root=path.join(__dirname,'../control-center/static');
const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
assert.match(html,/id="animation-publish-all"/);
assert.match(html,/id="animation-publish-queue-bar"/);
assert.match(html,/animation-publish-queue-core\.js\?v=474/);

async function run(){
  const order=[],states=[];
  const queue=core.create(async row=>{order.push(row.clipId);if(row.clipId==='bad')throw Error('roblox open cloud http 500: unknown error');},s=>states.push(s));
  const promise=queue.start([{clipId:'common',name:'common'},{clipId:'common'},{clipId:'bad'},{clipId:'female'}]);
  const outcome=await promise;
  assert.deepEqual(order,['common','bad']);
  assert.equal(outcome.total,3);
  assert.equal(outcome.published,1);
  assert.equal(outcome.failed,'bad');
  assert.equal(outcome.pending,1);
  assert.equal(outcome.items[2].status,'pending');
  assert.equal(outcome.items[1].status,'failed');
  assert.match(outcome.items[1].error,/500/);
  assert.equal(states.some(s=>s.items[0]?.status==='uploading'),true);
  const next=await queue.continuePending();
  assert.deepEqual(order,['common','bad','female']); // no automatic retry
  assert.equal(next.published,2);
  assert.equal(next.pending,0);
  assert.equal(next.items[1].status,'failed');

  let resolveActive;
  const stopped=core.create(async()=>new Promise(resolve=>{resolveActive=resolve}));
  const active=stopped.start([{clipId:'a'},{clipId:'b'}]);
  await new Promise(setImmediate);
  stopped.stop();resolveActive();
  const stoppedResult=await active;
  assert.equal(stoppedResult.published,1);
  assert.equal(stoppedResult.pending,1);
  assert.equal(stoppedResult.stopped,true);
  const resumed=stopped.continuePending();
  await new Promise(setImmediate);resolveActive();
  assert.equal((await resumed).published,2);

  // UI adapter: Publish All obtains authoritative all-character queue, handles failure,
  // and continues without retrying the possibly created asset.
  const elements={};
  function el(id){return elements[id]||(elements[id]={hidden:false,disabled:false,onclick:null,innerHTML:'',textContent:'',value:0,max:1});}
  const requests=[];
  const browser={
    window:{game1AnimationPublishQueueCore:core},document:{getElementById:el},
    confirm:()=>true,
  };
  vm.runInNewContext(fs.readFileSync(path.join(root,'animation-publish-queue.js'),'utf8'),browser);
  const adapter={
    state:()=>({animationPublishing:false}),render:()=>{},load:async()=>{},
    toast:()=>{},
    request:async(url)=>{
      requests.push(url);
      if(url==='/api/animations/publish-queue')return {items:[{clipId:'c',name:'common'},{clipId:'err',name:'err'},{clipId:'f',name:'female'}],publication:{configured:true}};
      if(url.includes('/err/'))throw Error('roblox open cloud http 500');
      return {asset_id:'12345',status:'PUBLISHED'};
    }
  };
  // state adapter must preserve its busy flag.
  const state={animationPublishing:false};adapter.state=()=>state;
  browser.window.game1AnimationPublishQueue.init(adapter);
  await browser.window.game1AnimationPublishQueue.publishAll();
  assert.deepEqual(requests.filter(x=>x.includes('/publish')),['/api/animations/publish-queue','/api/animations/c/publish','/api/animations/err/publish']);
  assert.equal(el('animation-publish-queue').hidden,false);
  assert.match(el('animation-publish-queue-message').textContent,/проверк/);
  assert.equal(el('animation-publish-continue').hidden,false);
  await el('animation-publish-continue').onclick();
  assert.equal(requests.filter(x=>x==='/api/animations/err/publish').length,1);
  assert.equal(requests.filter(x=>x==='/api/animations/f/publish').length,1);
  console.log('m474 animation publish queue: ok');
}
run().catch(err=>{console.error(err);process.exitCode=1;});
