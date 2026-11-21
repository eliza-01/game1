'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const nodes=new Map();
const node=id=>{
  if(!nodes.has(id))nodes.set(id,{hidden:false,disabled:false,textContent:'',innerHTML:'',checked:false,
    value:'',addEventListener(type,handler){this['on_'+type]=handler;},setAttribute(){}});
  return nodes.get(id);
};
const settings={distances:{lod1:120,lod2:260,hide:400,hysteresis:12},
  workspace:{streamingEnabled:true,minRadius:64,targetRadius:1024,modelStreamingBehavior:'Improved',
    streamingIntegrityMode:'PauseOutsideLoadedArea',streamOutBehavior:'Opportunistic'}};
const house={slug:'house_level5_01',count:40,mode:'lod1',fullStatus:'PUBLISHED',
  profile:{mode:'lod1',revision:2},ready:true,warnings:[],
  parts:[{name:'roof',color:'#FF1100',appearance:'material'},{name:'walls_outside',color:'#00BB22',appearance:'material'}],
  partLod1:{roof:{status:'PUBLISHED',revision:2,modelAssetId:'12345'},
    walls_outside:{status:'NOT_REGISTERED',revision:0,modelAssetId:''}},
  partStreaming:{roof:{lod1:150,hide:500,revision:1},walls_outside:{lod1:120,hide:400,revision:1}}};
const data={settings,snapshot:{revisionId:1,recordedUtc:1,fingerprint:'a'.repeat(64),placeId:0,
  freshness:'SCANNED_THIS_SESSION',catalogMatches:true,warnings:[]},
  summary:{placements:0,typesWithPlacements:0,registeredTypes:0,lod1Types:0,missingId:0,duplicateId:0,
    ambiguous:0,noModel:0,collisionReview:0,scanWarnings:0},items:[],realEstate:{items:[house]},revisions:[],
  build:{canPreflight:false,sourceFile:'source.rbxlx'}};
const writes=[];
const sandbox={document:{getElementById:node},window:{},navigator:{clipboard:{writeText:()=>Promise.resolve()}},
  request:async(url,options)=>{
    if(url==='/api/lod-manager')return data;
    writes.push({url,payload:JSON.parse(options.body)});
    if(url.endsWith('/distances')){
      const item=house.partStreaming.roof;
      Object.assign(item,writes.at(-1).payload.distances,{revision:item.revision+1});
    }
    return data;
  }};
vm.runInNewContext(fs.readFileSync('system/control-center/static/lod-manager.js','utf8'),sandbox);
const ticks=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 await sandbox.window.game1LodManagerLoad();
 node('lod-tab-house').on_click();
 assert(node('lod-house-rows').innerHTML.includes('data-part-distance="lod1"'));
 assert(node('lod-house-rows').innerHTML.includes('data-part-distance="hide"'));
 assert(node('lod-house-rows').innerHTML.includes('Save distances'));
 assert(!node('lod-house-rows').innerHTML.includes('Save house distances'));
 assert(!node('lod-house-rows').innerHTML.includes('data-house-setting'));
 const section={querySelector:selector=>({value:selector.includes('lod1')?'200':'700'})};
 const button={dataset:{partDistanceSave:'roof',partHouse:house.slug},closest:selector=>{
   if(selector==='button[data-part-distance-save]')return button;
   if(selector==='.lm-house-part')return section;
   return null;
 }};
 node('lod-house-rows').on_click({target:button});await ticks();await ticks();
 assert.equal(writes.length,1);
 assert.equal(writes[0].url,`/api/real-estate/${house.slug}/parts/roof/distances`);
 assert.equal(writes[0].payload.expectedRevision,1);
 assert.equal(writes[0].payload.distances.lod1,200);
 assert.equal(writes[0].payload.distances.hide,700);
 assert.equal(house.partStreaming.walls_outside.lod1,120);
 assert.equal(house.partStreaming.roof.revision,2);
 assert.equal(node('lod-build-execute').hidden,true);
 console.log('M414 part distance editor: OK');
})().catch(e=>{console.error(e);process.exitCode=1;});
