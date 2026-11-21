'use strict';
const assert=require('assert');
const fs=require('fs');
const vm=require('vm');
const html=fs.readFileSync('system/control-center/static/index.html','utf8');
for(const id of ['lod-readiness-section','lod-tab-location','lod-tab-house',
                 'lod-location-panel','lod-house-panel','lod-house-rows','lod-house-message']){
  assert(html.includes(`id="${id}"`),id);
}
assert(!html.includes('id="lod-real-estate-section"'), 'duplicate Real Estate section');
assert(html.indexOf('lod-house-panel') < html.indexOf('lod-settings-section'), 'house UI not inside 02');
const nodes=new Map();
const node=id=>{
 if(!nodes.has(id))nodes.set(id,{hidden:false,disabled:false,innerHTML:'',textContent:'',value:'',checked:false,
   addEventListener(kind,fn){this['on_'+kind]=fn;},setAttribute(name,value){this[name]=value;}});
 return nodes.get(id);
};
const settings={distances:{lod1:120,lod2:260,hide:400,hysteresis:12},
  workspace:{streamingEnabled:true,minRadius:64,targetRadius:1024,modelStreamingBehavior:'Improved',
    streamingIntegrityMode:'PauseOutsideLoadedArea',streamOutBehavior:'Opportunistic'}};
const data={snapshot:{revisionId:3,recordedUtc:1,fingerprint:'a'.repeat(64),placeId:0, freshness:'NOT_LIVE_VERIFIED',catalogMatches:true,warnings:[]},
  settings,summary:{placements:4,typesWithPlacements:1,registeredTypes:1,lod1Types:0,missingId:0,duplicateId:0,ambiguous:0,noModel:0,collisionReview:0,scanWarnings:0},
  items:[{slug:'torch_01',count:4,category:'light',streamingMode:'auto',indicator:'red',lod1Status:'NOT_REGISTERED',issues:{},streamingEligible:true}],
  realEstate:{selected:1,placements:40,items:[{slug:'house_level5_01',count:40,mode:'full',fullStatus:'PUBLISHED',
    profile:{mode:'full',revision:1},ready:true,warnings:[],
    parts:[{name:'roof',fullDistance:100,distanceStreaming:true,appearance:'material_atlas',color:'#FF1100'},
           {name:'wall',fullDistance:100,distanceStreaming:true,appearance:'material',color:'#00BB22'}],
    partStreaming:{roof:{lod1:100,hide:500,revision:1},wall:{lod1:100,hide:300,revision:1}},
    partLod1:{roof:{status:'NOT_REGISTERED',revision:0,modelAssetId:''},wall:{status:'PUBLISHED',revision:1,modelAssetId:'123456'}}}]},
  revisions:[],build:{canPreflight:false,sourceFile:'source.rbxlx'}};
let chosen=false;
const ctx={document:{getElementById:node},window:{game1LodReusePicker:{pick:async()=>null,payload:()=>null}},
  navigator:{clipboard:{writeText:async()=>{}}},request:async(path, opts)=>{
    if(path==='/api/lod-manager')return data;
    if(path==='/api/files/choose-real-estate-model'){
      chosen=true;return {path:'c:/house_level5_01_roof_lod1.fbx'};
    }
    if(path.endsWith('/lod1-stage')){
      assert(chosen);const body=JSON.parse(opts.body);
      assert.strictEqual(body.expectedRevision,0);
      assert(body.sourcePath.includes('roof_lod1.fbx'));
      data.realEstate.items[0].partLod1.roof={status:'STAGED',revision:1,modelAssetId:''};
      return {lod1:data.realEstate.items[0].partLod1.roof};
    }
    return data;
  }};
vm.runInNewContext(fs.readFileSync('system/control-center/static/lod-manager.js','utf8'),ctx);
(async()=>{
 await ctx.window.game1LodManagerLoad();
 assert(node('lod-rows').innerHTML.includes('torch_01'));
 assert(node('lod-house-panel').hidden);
 assert.strictEqual(node('lod-tab-location').textContent,'Location Assets · 1 видов');
 assert.strictEqual(node('lod-tab-house').textContent,'Real Estate · 1 видов');
 node('lod-tab-house').on_click();
 assert(node('lod-location-panel').hidden);
 assert(!node('lod-house-panel').hidden);
 assert.strictEqual(node('lod-tab-house')['aria-selected'],'true');
 assert(node('lod-house-rows').innerHTML.includes('roof'));
 assert(node('lod-house-rows').innerHTML.includes('wall'));
 assert(node('lod-house-rows').innerHTML.includes('#FF1100'));
 assert(node('lod-house-rows').innerHTML.includes('1 / 2 LOD1 parts'));
 assert(node('lod-house-rows').innerHTML.includes('Save distances'));
 assert(node('lod-house-rows').innerHTML.includes('data-part-distance="lod1"'));
 const click=(kind)=>node('lod-house-rows').on_click({target:{closest:(selector)=>selector==='button[data-part-action]' ? ({dataset:{partAction:kind,partSlug:'house_level5_01',partName:'roof'}}) : null}});
 click('choose');
 await new Promise(resolve=>setImmediate(resolve));
 assert(node('lod-house-rows').innerHTML.includes('house_level5_01_roof_lod1.fbx'));
 click('stage');
 await new Promise(resolve=>setImmediate(resolve));
 assert(node('lod-house-rows').innerHTML.includes('STAGED'));
 node('lod-tab-location').on_click();
 assert(!node('lod-location-panel').hidden);
 console.log('M412 LOD readiness domain tabs and house part actions: OK');
})().catch(error=>{console.error(error);process.exitCode=1});
