const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
function node(tag='div') {return {tag,value:'',textContent:'',hidden:false,disabled:false,children:[],
  appendChild(child){this.children.push(child)},replaceChildren(){this.children=[]},setAttribute(){}}}
const dialog=node('dialog');dialog.open=false;
const controls={};
const selector=name=>controls[name]||(controls[name]=node());
const radio=[{value:'preserve',checked:false},{value:'all',checked:false}];
dialog.querySelector=s=>selector(s);
dialog.querySelectorAll=s=>s==='[name="shared-retirement-mode"]'?radio:[];
dialog.showModal=()=>{dialog.open=true};dialog.close=()=>{dialog.open=false};
const document={body:{appendChild(c){assert.equal(c,dialog)}},createElement(tag){
  if(['dialog','p','ul','li','h4','section'].includes(tag))return tag==='dialog'?dialog:node(tag);
  throw Error(tag);
}};
const calls=[];let done=0;
const plan={root:'estate:house_level4_01',dependentCount:3,token:'safe-token',
 nodes:[{kind:'estate',slug:'house_level5_01'}, {kind:'estate',slug:'house_level6_01'},
  {kind:'estate',slug:'house_level7_01'},
  {kind:'estate',slug:'house_level4_01',textures:{house:{assetId:'130840873415092',filename:'house_01_512x512_atlas.png'},roof:{assetId:'456',filename:'roof_01_256x256_atlas.png'}}}],
 relations:[
  {owner:'estate:house_level4_01',ownerPart:'house',dependent:'estate:house_level5_01',part:'door'},
  {owner:'estate:house_level4_01',ownerPart:'house',dependent:'estate:house_level5_01',part:'windows'},
  {owner:'estate:house_level4_01',ownerPart:'house',dependent:'estate:house_level6_01',part:'door'},
  {owner:'estate:house_level4_01',ownerPart:'roof',dependent:'estate:house_level7_01',part:'roof'},
 ]};
let nextPlan=plan;
async function request(path,args){
 if(path.includes('impact'))return nextPlan;
 calls.push(JSON.parse(args.body));
 return {deleted:[{slug:args.body.slug}]};
}
const window={};
const context=vm.createContext({document,window,request});
vm.runInContext(fs.readFileSync(process.argv[3],'utf8'),context);
vm.runInContext(fs.readFileSync(process.argv[2],'utf8'),context);
(async()=>{
 await window.game1AssetRetirement.open({kind:'estate',slug:'house_level4_01',onDone:async()=>{done++}});
 assert.equal(radio[0].checked,true);
 assert.equal(selector('[data-retirement-confirm-label]').hidden,true);
 assert.equal(selector('[data-retirement-submit]').disabled,false);
 assert.equal(selector('[data-retirement-submit]').textContent,'Delete house · keep shared assets');
 const depChildren=selector('[data-retirement-dependencies]').children;
 const groups=depChildren.filter(child=>child.className==='shared-asset-retirement-source');
 assert.equal(groups.length,2,'two different reused source textures must be separated');
 const house=groups.find(child=>child.children[0].textContent==='Shared atlas · house_01');
 const roof=groups.find(child=>child.children[0].textContent==='Shared atlas · roof_01');
 assert.ok(house);assert.ok(roof);
 assert.equal(house.children[1].textContent,'house · variant 01 · 512×512 · Image Asset ID: 130840873415092');
 assert.equal(house.children[2].textContent,'Used by 3 part(s) in 2 registration(s):');
 assert.deepEqual(house.children[3].children.map(li=>li.textContent),[
  'estate:house_level5_01 / door','estate:house_level5_01 / windows',
  'estate:house_level6_01 / door']);
 assert.equal(roof.children[1].textContent,'roof · variant 01 · 256×256 · Image Asset ID: 456');
 assert.equal(roof.children[3].children.length,1);
 await selector('[data-retirement-submit]').onclick();
 assert.equal(calls[0].mode,'preserve');assert.equal(calls[0].token,'safe-token');
 assert.equal(done,1);
 await window.game1AssetRetirement.open({kind:'estate',slug:'house_level4_01',onDone:async()=>{done++}});
 radio[0].checked=false;radio[1].checked=true;radio[1].onchange();
 assert.equal(selector('[data-retirement-submit]').textContent,'Delete all (4 registrations)');
 assert.equal(selector('[data-retirement-submit]').disabled,true);
 selector('[data-retirement-confirm]').value='wrong';
 selector('[data-retirement-confirm]').oninput();
 assert.equal(selector('[data-retirement-submit]').disabled,true);
 selector('[data-retirement-confirm]').value='house_level4_01';
 selector('[data-retirement-confirm]').oninput();
 assert.equal(selector('[data-retirement-submit]').disabled,false);
 await selector('[data-retirement-submit]').onclick();
 assert.equal(calls[1].mode,'all');assert.equal(done,2);
 nextPlan={root:'location:tree_01',dependentCount:0,token:'empty-token',
  nodes:[{kind:'location',slug:'tree_01'}],relations:[]};
 await window.game1AssetRetirement.open({kind:'location',slug:'tree_01',onDone:async()=>{done++}});
 assert.equal(selector('[data-retirement-submit]').textContent,'Delete location asset');
 assert.equal(selector('[data-retirement-submit]').disabled,false);
 // Location dependency must resolve the source as a texture, not a model part.
 nextPlan={root:'location:tree_01',dependentCount:1,token:'location-token',
  nodes:[{kind:'estate',slug:'house_level4_01'},
    {kind:'location',slug:'tree_01',textureId:'987654321',textureFilename:'structures_01_1024x512_atlas.png'}],
  relations:[{owner:'location:tree_01',ownerPart:'',dependent:'estate:house_level4_01',part:'door'}]};
 await window.game1AssetRetirement.open({kind:'location',slug:'tree_01',onDone:async()=>{done++}});
 const locationGroups=selector('[data-retirement-dependencies]').children.filter(child=>child.className==='shared-asset-retirement-source');
 assert.equal(locationGroups.length,1);
 assert.equal(locationGroups[0].children[0].textContent,'Shared atlas · structures_01');
 assert.equal(locationGroups[0].children[1].textContent,'structures · variant 01 · 1024×512 · Image Asset ID: 987654321');
 assert.equal(selector('[data-retirement-submit]').textContent,'Delete location asset · keep shared assets');
 console.log('m200 modal dynamic actions, grouped reused atlases, estate/location, safe default: OK');
})().catch(e=>{console.error(e);process.exitCode=1});
