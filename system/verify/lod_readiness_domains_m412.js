'use strict';
const assert=require('assert');
const fs=require('fs');
const vm=require('vm');
const html=fs.readFileSync('system/control-center/static/index.html','utf8');
for(const id of ['lod-readiness-section','lod-tab-location','lod-tab-house',
                 'lod-location-panel','lod-house-panel','lod-house-rows','lod-house-message',
                 'lod-house-search','lod-house-filter']){
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
let navigation=null;
const ctx={document:{getElementById:node},window:{game1RealEstateOpenLod1:(slug,part)=>{navigation={slug,part}}},
  navigator:{clipboard:{writeText:async()=>{}}},request:async(path)=>{
    if(path==='/api/lod-manager')return data;
    throw Error('LOD Manager must not upload or publish house FBX: '+path);
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
 const markup=node('lod-house-rows').innerHTML;
 assert(markup.includes('roof'));
 assert(markup.includes('wall'));
 assert(markup.includes('Крыша и проёмы'));
 assert(markup.includes('Стены и конструкции'));
 assert(markup.includes('data-part-distance="lod1"'));
 assert(markup.includes('data-part-distance="hide"'));
 assert(markup.includes('data-house-lod-edit="house_level5_01"'));
 assert(!markup.includes('data-part-action='), 'no LOD upload controls in Manager');
 for(const label of ['Choose FBX','Stage FBX','Publish LOD1','Use published LOD1'])
   assert(!markup.includes(label),label);
 const button={dataset:{houseLodEdit:'house_level5_01',houseLodPart:'roof'},
   closest:selector=>selector==='button[data-house-lod-edit]'?button:null};
 node('lod-house-rows').on_click({target:button});
 assert.deepStrictEqual(navigation,{slug:'house_level5_01',part:'roof'});
 node('lod-tab-location').on_click();
 assert(!node('lod-location-panel').hidden);
 console.log('M412 LOD readiness domain tabs and house part actions: OK');
})().catch(error=>{console.error(error);process.exitCode=1});
