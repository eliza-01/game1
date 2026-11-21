'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const script=fs.readFileSync(path.resolve(__dirname,'../control-center/static/lod-reuse-picker.js'),'utf8');
class El {
  constructor(tag){this.tagName=tag;this.children=[];this.events={};this.value=(tag==='select'?'all':'');this.style={};this.textContent='';}
  append(...xs){this.children.push(...xs);}
  appendChild(x){this.children.push(x);}
  replaceChildren(...xs){this.children=xs;}
  setAttribute(k,v){this[k]=v;}
  addEventListener(k,cb){this.events[k]=cb;}
  close(){this.closed=true;}
  remove(){this.removed=true;}
  showModal(){this.open=true;}
  focus(){}
}
(async()=>{
  const body=new El('body');
  const context={window:{},document:{body,createElement:tag=>new El(tag)},request:async()=>({items:[
    {domain:'location',slug:'lantern_01',revision:1,modelAssetId:'111'},
    {domain:'location',slug:'lantern_02',revision:2,modelAssetId:'222'},
    {domain:'house',slug:'house_level5_01',revision:1,modelAssetId:'333'},
  ]})};
  vm.runInNewContext(script,context);
  const picker=context.window.game1LodReusePicker;
  const p=picker.pick('location','lantern_01');
  await new Promise(resolve=>setImmediate(resolve));
  const dialog=body.children[0];
  assert.equal(dialog.open,true);
  const list=dialog.children.find(x=>x.className==='lod-reuse-list');
  assert.equal(list.children.length,2,'should exclude current owner');
  const chosen=list.children[1];
  chosen.children[1].onclick();
  const result=await p;
  assert.equal(result.slug,'house_level5_01');
  assert.equal(dialog.removed,true);
  assert.equal(picker.payload(result,4).expectedRevision,4);
  assert.equal(picker.payload(result,4).sourceModelAssetId,'333');
  const second=picker.pick('house','house_level5_01');
  await new Promise(resolve=>setImmediate(resolve));
  const d=body.children[1];
  d.children[d.children.length-1].onclick();
  assert.equal(await second,null);
  console.log('M411 LOD reuse picker: OK');
})().catch(error=>{console.error(error);process.exitCode=1;});
