/* M254: an unpublished attached dot invites first publication, not a variant switch. */
const fs=require('node:fs'), vm=require('node:vm'), assert=require('node:assert/strict');
const path=require('node:path');
const source=fs.readFileSync(path.resolve(__dirname,'../control-center/static/asset-atlas-editor.js'),'utf8');
const ctx={window:{},esc:s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;')};
vm.createContext(ctx);vm.runInContext(source,ctx);
const editor=ctx.window.game1ConsumerAtlasEditor;
const active={id:11,filename:'bush_02_256x256_atlas.png',resolution:'256x256',width:256,height:256,published_id:'999',current:true};
const pending={id:12,filename:'bush_02_512x512_atlas.png',resolution:'512x512',width:512,height:512,published_id:null,current:false};
const opts={currentId:11,linked:[active,pending],catalog:[],offerPublication:true};
const state=editor.newState();
const html=editor.render(state,opts);
const dot=html.match(/<button[^>]*data-ca-choice="12"[^>]*>/)?.[0];
assert(dot,'unpublished dot must be visible');
assert.match(dot,/data-ca-offer-publication/);
assert.doesNotMatch(dot,/\sdisabled(?:=|\s|>)/);
assert.match(dot,/Нажмите, чтобы предложить публикацию/);
// When embedded in the Real Estate editor without this capability, keep its guard.
const estate=editor.render(editor.newState(),{...opts,offerPublication:false});
assert.match(estate.match(/<button[^>]*data-ca-choice="12"[^>]*>/)[0],/disabled/);
let renders=0,published=[];
const pendingDot={dataset:{caChoice:'12'},hasAttribute:key=>key==='data-ca-offer-publication'};
const offerButton={};const cancelButton={};
const container={
 querySelectorAll:s=>s==='[data-ca-choice]'?[pendingDot]:[],
 querySelector:s=>s==='[data-ca-publish-offer]'&&state.publicationOfferId?offerButton:
   s==='[data-ca-cancel-offer]'&&state.publicationOfferId?cancelButton:null,
};
const callbacks={consumerType:'location_asset',slug:'bush_02',onRender:()=>{renders++;},
 onPublishAtlas:async id=>{published.push(id);return true;},onMessage:()=>{},onRefresh:async()=>{}};
editor.wire(container,state,callbacks);
pendingDot.onclick();
assert.equal(state.publicationOfferId,12);
assert.match(editor.render(state,opts),/Опубликовать атлас\?/);
assert.match(editor.render(state,opts),/data-ca-publish-offer/);
editor.wire(container,state,callbacks);
(async()=>{
  await offerButton.onclick();
  assert.deepEqual(published,[12]);
  assert.equal(state.publicationOfferId,0);
  assert(renders>=2);
  console.log('M254 unpublished dot offer: OK');
})().catch(err=>{console.error(err);process.exitCode=1;});
