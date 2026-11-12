'use strict';
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const root=path.resolve(__dirname,'../control-center/static');
let toastMessages=[];
global.window=global;
global.esc=x=>String(x??'').replace(/[&<>"']/g,x=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));
global.toast=(msg)=>toastMessages.push(msg);
global.confirm=()=>true;
const entries=new Map();
const host=id=>{
 if(!entries.has(id)){
  const e={innerHTML:'', querySelectorAll:()=>[], querySelector:(selector)=> {
    if(selector==='[data-wa-clear]'||selector==='[data-wa-refresh]') return {onclick:null};
    return null;
  }};
  entries.set(id,e);
 }
 return entries.get(id);
};
global.$=host;
const variant=(id,size)=>({id,filename:`lamp_01_${size}x${size}_atlas.png`,original_filename:`lamp_01_${size}x${size}_atlas.png`,
    published_id:String(60000+id),resolution:`${size}x${size}`,width:size,height:size,current:true,atlasKey:'lamp_01'});
let currentCatalog=[{atlasKey:'lamp_01',variants:[variant(2,512),variant(3,128)]}];
let choiceCalls=[];
global.request=async (url,opts={})=> {
 if(url==='/api/texture-atlases')return {families:currentCatalog};
 if(url==='/api/texture-atlases/consumer-choice') {
   choiceCalls.push(JSON.parse(opts.body));return {item:{}};
 }
 if(url==='/api/texture-atlases/index-existing-weapons')return {indexed:[{key:'weapon_lamp'}],skipped:[]};
 if(url==='/api/weapons')return {items:[]};
 throw Error('Unexpected network endpoint '+url);
};
for(const name of ['asset-atlas-editor.js','weapon-atlas-picker.js'])
 vm.runInThisContext(fs.readFileSync(path.join(root,name),'utf8'),{filename:name});
const expected=window.game1ConsumerAtlasEditor.render(window.game1ConsumerAtlasEditor.newState(),{
 currentId:2,linked:[variant(2,512),variant(3,128)],catalog:currentCatalog});
assert.strictEqual((expected.match(/class="deco-atlas-dot(?:\s|")/g)||[]).length,2,expected);
assert(expected.includes('is-active'), 'selected resolution must be active');
assert(expected.includes('512x512')&&expected.includes('128x128'));
const legacy={slug:'old',textures:[{source_path:'weapons/old_texture.png',asset_id:'987654'}],atlas_variants:[],atlas_binding:null};
(async()=>{
 await window.game1WeaponAtlasPicker.refresh();
 window.game1WeaponAtlasPicker.render('weapon-atlas-picker','weapon',legacy,async()=>{});
 const markup=host('weapon-atlas-picker').innerHTML;
 assert(markup.includes('data-ca-import-legacy'),markup);
 assert(markup.includes('deco-atlas-dot'),markup);
 assert.strictEqual((markup.match(/class="deco-atlas-dot(?:\s|")/g)||[]).length,1,markup);
 assert(markup.includes('987654'),markup);
 assert(markup.includes('Legacy atlas'),markup);
 assert(markup.includes('Upload new atlas'),markup);
 const arrow={slug:'steel',texture_path:'arrow.png',texture_asset_id:'1234',atlas_variants:[],atlas_binding:null};
 window.game1WeaponAtlasPicker.render('arrow-atlas-picker','arrow',arrow,async()=>{});
 assert(host('arrow-atlas-picker').innerHTML.includes('data-ca-import-legacy'));
 // Location-style graduation: only 512 is attached, but 128 is
 // discoverable as a same-family dot. This must not mutate any binding.
 const single={slug:'only_large',textures:[],atlas_binding:{id:2,revision:1,published_id:'60002',filename:'lamp_01_512x512_atlas.png',atlas_key:'lamp_01'},
   atlas_variants:[variant(2,512)]};
 window.game1WeaponAtlasPicker.render('weapon-atlas-picker','weapon',single,async()=>{});
 const grades=host('weapon-atlas-picker').innerHTML;
 assert.strictEqual((grades.match(/class="deco-atlas-dot(?:\s|")/g)||[]).length,2,grades);
 assert(grades.includes('data-ca-connect-resolution'),grades);
 assert(!choiceCalls.length,'discovering a resolution must not attach or select silently');
 const linked={slug:'old',textures:legacy.textures,atlas_binding:{id:2,revision:1,published_id:'60002',filename:'lamp_01_512x512_atlas.png'},
   atlas_variants:[variant(2,512),variant(3,128)]};
 window.game1WeaponAtlasPicker.render('weapon-atlas-picker','weapon',linked,async()=>{});
 const result=host('weapon-atlas-picker').innerHTML;
 assert.strictEqual((result.match(/class="deco-atlas-dot(?:\s|")/g)||[]).length,2,result);
 assert(!result.includes('Legacy atlas / нестандартное имя'),'standardized active atlas must not be labelled legacy');
 assert(!choiceCalls.length,'rendering must not submit network mutations');
 console.log('M308 UI smoke: 2 resolution dots, legacy weapon/arrow dots, active state, upload action, no silent mutation: OK');
})().catch(err=>{console.error(err);process.exitCode=1});
