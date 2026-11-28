'use strict';
// DOM/transport double: authoring workflow, not a browser or Roblox test.
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');
const html = fs.readFileSync('system/control-center/static/index.html','utf8');
for(const id of ['lod-tab-mnpc','lod-mnpc-panel','mnpc-lod-rows','mnpc-lod-defaults','mnpc-lod-editor'])
  assert(html.includes(`id="${id}"`));
const elements=new Map();
function get(id){assert.notEqual(id,'mnpc-lod-panel','use actual panel ID');if(!elements.has(id))elements.set(id,{innerHTML:'',textContent:'',value:'',disabled:false,dataset:{},
  querySelectorAll(){return [];},addEventListener(name,fn){this['on_'+name]=fn;}});return elements.get(id);}
const profile={enabled:false,full:100,hide:200,hysteresis:10};
const make=(kind)=>({kind,slug:'same',name:kind==='monster'?'Gremlin <unsafe>':'Guard',fullStatus:'PUBLISHED',fullModelId:'123',fullRevision:2,
  status:'NOT_REGISTERED',fullFingerprint:kind+'-fingerprint',fullIdentity:{modelId:'123'},revision:0,profile,inherits:true});
const data={schemaVersion:1,runtimeEnabled:false,settings:{revision:0,defaults:profile,overrides:{}},items:[make('monster'),make('npc')]};
let captured={status:'NOT_CAPTURED'};
const posts=[],storage=new Map([['game1.lod.mnpc.filter','npc']]);
const ctx={document:{getElementById:get},window:{localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)}},request:async(url,opts={})=>{
  if(opts.method==='POST'){const p=JSON.parse(opts.body);posts.push([url,p]);
    if(url.endsWith('/capture')){captured={status:'CAPTURED',meshCount:3,boneCount:56,animationId:'123',pose:{time:0.35},captureSha256:'capture',geometryReady:true,triangleCount:1000};return captured;}
    if(url.endsWith('/bake')){const r=data.items[0];Object.assign(r,{status:'STAGED',revision:1,geometry:{vertices:10,triangles:8,boundsMin:[0,0,0],boundsMax:[1,1,2],preparation:{inputTriangles:1000,inputMeshes:3,outputTextureSize:[512,512],mode:'captured_idle'}}});return r;}
    if(url.endsWith('/prepare')){const r=data.items[0];Object.assign(r,{status:'STAGED',revision:2,geometry:{vertices:10,triangles:8,boundsMin:[0,0,0],boundsMax:[1,1,2],preparation:{inputTriangles:1000,inputMeshes:2,outputTextureSize:[512,256],mode:'posed_static'}}});return r;}
    if(url.endsWith('/stage')){const r=data.items[0];Object.assign(r,{status:'STAGED',revision:1,geometry:{vertices:10,triangles:8,boundsMin:[0,0,0],boundsMax:[1,1,2]}});return r;}
    if(url.endsWith('/publish')){Object.assign(data.items[0],{status:'MODEL_PENDING',modelOperation:'operations/test',imageAssetId:'1234'});throw Error('Cloud timeout');}
    if(url.endsWith('/settings')){data.settings.revision++;return data;}
    if(url.endsWith('/choose-location-asset-model'))return {path:'C:/same_lod1.fbx'};
    if(url.endsWith('/choose-character-atlas'))return {path:'C:/baked.png'};
  }
  if(url.endsWith('/capture'))return captured;
  if(url.endsWith('/history'))return {items:[]};
  return data;
}};
vm.runInNewContext(fs.readFileSync('system/control-center/static/mnpc-lod-manager.js','utf8'),ctx);
const click=(id,dataset)=>get(id).on_click({target:{closest:()=>({dataset})}});
(async()=>{
  await ctx.window.game1MnpcLod.load();
  assert(get('mnpc-lod-rows').innerHTML.includes('Guard'));
  assert(!get('mnpc-lod-rows').innerHTML.includes('Gremlin'));
  get('mnpc-lod-filter').value='all';get('mnpc-lod-filter').on_change();
  assert.equal(storage.get('game1.lod.mnpc.filter'),'all');
  assert(get('mnpc-lod-rows').innerHTML.includes('Gremlin &lt;unsafe&gt;'));
  await click('mnpc-lod-rows',{mnpcEdit:'monster:same'});
  assert(get('mnpc-lod-editor').innerHTML.includes('monster-fingerprint'));
  await click('mnpc-lod-editor',{mnpcAction:'capture'});
  assert.deepStrictEqual(posts.at(-1),['/api/lod-manager/mnpc/monster/same/capture',{expectedRevision:0,fullFingerprint:'monster-fingerprint',phase:0.35,includeGeometry:true}]);
  assert(get('mnpc-lod-editor').innerHTML.includes('Captured · 3 meshes · 56 bones'));
  await click('mnpc-lod-editor',{mnpcAction:'choose-fbx'});
  await click('mnpc-lod-editor',{mnpcAction:'choose-texture'});
  await click('mnpc-lod-editor',{mnpcAction:'stage'});
  assert.deepStrictEqual(posts.at(-1),['/api/lod-manager/mnpc/monster/same/stage',{sourcePath:'C:/same_lod1.fbx',texturePath:'C:/baked.png',expectedRevision:0,fullFingerprint:'monster-fingerprint'}]);
  assert(get('mnpc-lod-editor').innerHTML.includes('8 triangles'));
  get('mnpc-bake-targetTriangles').value='1000';get('mnpc-bake-textureSize').value='512';
  await click('mnpc-lod-editor',{mnpcAction:'bake'});
  assert.deepStrictEqual(posts.at(-1),['/api/lod-manager/mnpc/monster/same/bake',{expectedRevision:1,fullFingerprint:'monster-fingerprint',captureSha256:'capture',targetTriangles:1000,textureSize:512}]);
  assert(get('mnpc-lod-editor').innerHTML.includes('captured_idle'));
  await click('mnpc-lod-editor',{mnpcAction:'choose-pose'});
  await click('mnpc-lod-editor',{mnpcAction:'choose-pose-atlas'});
  get('mnpc-prepare-frame').value='1';get('mnpc-prepare-targetTriangles').value='1000';get('mnpc-prepare-textureSize').value='512';get('mnpc-prepare-reviewedAssembly').checked=true;
  await click('mnpc-lod-editor',{mnpcAction:'prepare'});
  assert.deepStrictEqual(posts.at(-1),['/api/lod-manager/mnpc/monster/same/prepare',{posePath:'C:/same_lod1.fbx',texturePath:'C:/baked.png',frame:1,targetTriangles:1000,textureSize:512,reviewedAssembly:true,expectedRevision:1,fullFingerprint:'monster-fingerprint'}]);
  assert(get('mnpc-lod-editor').innerHTML.includes('1000 → 8 tri'));
  await click('mnpc-lod-editor',{mnpcAction:'publish'});
  assert.equal(get('mnpc-lod-message').textContent,'Cloud timeout');
  assert(get('mnpc-lod-editor').innerHTML.includes('Resume operation'));
  assert(get('mnpc-lod-editor').innerHTML.includes('1234'));
  console.log('MNPC authoring UI: filters, identity, stage, partial publication refresh OK');
})().catch(error=>{console.error(error);process.exitCode=1;});
