// Exercise ranking, component table ordering and atlas family sections with the real browser scripts.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const policy=require(process.argv[2]);

const catalog={
  atlas_families:[
    {atlasKey:'newborn_upper',variants:[
      {id:31,width:256,height:256,current:true,published_id:'31'},
      {id:30,width:512,height:512,current:true,published_id:'30'},
      {id:32,width:128,height:128,current:false,published_id:''},
    ]},
    {atlasKey:'head_01_male',variants:[{id:11,width:512,height:512,current:true,published_id:'11'}]},
    {atlasKey:'newborn_lower',variants:[
      {id:14,width:512,height:512,current:true,published_id:'14'},
      {id:15,width:1024,height:512,current:true,published_id:'15'},
    ]},
    {atlasKey:'newborn_boots',variants:[{id:12,width:512,height:512,current:true,published_id:'12'}]},
  ],
  publication:{configured:true},
  items:[
    {id:'head_01_male',kind:'part',slot:'head',set_id:'',rig_id:'human',revision:1,
      published_revision:1,model_asset_id:'123',status:'published',atlas:{variant_id:11,revision:1,current:true}},
    {id:'newborn_lower',kind:'part',slot:'lower',set_id:'newborn',rig_id:'human',revision:2,
      published_revision:1,model_asset_id:'200',status:'replacement_pending',atlas:{variant_id:14,revision:1,current:true}},
    {id:'newborn_upper',kind:'part',slot:'upper',set_id:'newborn',rig_id:'human',revision:1,
      published_revision:0,model_asset_id:'',status:'registered',atlas:{variant_id:31,revision:1,current:true}},
  ]
};
const groups=policy.orderedFamilies(catalog.atlas_families);
assert.deepEqual(groups.map(g=>g.atlasKey),['head_01_male','newborn_boots','newborn_lower','newborn_upper']);
assert.deepEqual(groups.find(g=>g.atlasKey==='newborn_upper').variants.map(v=>v.id),[30,31,32]);
assert.deepEqual(groups.find(g=>g.atlasKey==='newborn_upper').variants.map(v=>v.rank),[0,1,2]);
assert.equal(groups.find(g=>g.atlasKey==='newborn_upper').variants[0].color,'#d9ac43');
assert.deepEqual(policy.optionsForPart('newborn_lower',catalog.atlas_families).slice(0,2).map(v=>v.id),[15,14]);
assert.deepEqual(policy.optionsForPart('newborn_upper',catalog.atlas_families).slice(0,3).map(v=>v.id),[30,31,32]);
assert.equal(policy.variantRank(catalog.atlas_families,31),1);
assert.equal(policy.variantRank(catalog.atlas_families,999),null);
assert.equal(policy.matchesPart,undefined,'presentation API stays narrow');

class Element {
  constructor(tag='div'){
    this.tagName=tag;this.children=[];this.dataset={};this.attributes={};this.textContent='';
    this.value='';this.disabled=false;this.parentElement=null;this.classList={toggle(){}};
  }
  append(...kids){for(const child of kids){this.children.push(child);if(child&&typeof child==='object')child.parentElement=this;}}
  replaceChildren(...kids){this.children=[];this.append(...kids);}
  setAttribute(key,value){this.attributes[key]=String(value);}
  addEventListener(){}
  querySelector(selector){if(selector==='option')return this.children.find(e=>e.tagName==='option')||null;return null;}
  querySelectorAll(selector){const result=[];const walk=node=>{for(const c of node.children||[]){
    if(selector==='[data-cp-atlas-select]'&&Object.hasOwn(c.dataset,'cpAtlasSelect'))result.push(c);
    walk(c);
  }};walk(this);return result;}
}
const elements=new Map();
const document={getElementById(id){if(!elements.has(id))elements.set(id,new Element());return elements.get(id);},
  createElement(tag){return new Element(tag);},querySelectorAll(){return []}};
const context=vm.createContext({document,window:{
  game1CharacterAtlasPresentation:policy,
  game1CharacterPublications:{configure(){},selectionCell(){return new Element('td');},
    button(){return new Element('button');},setBusy(){},isRunning(){return false;}},
  game1CharacterComponentSummary:{render(){}},
  addEventListener(){},dispatchEvent(){},
},Event:class Event{constructor(type){this.type=type;}},
  Option:function Option(label,value){const item=new Element('option');item.textContent=label;item.value=String(value);return item;},
  request(url){if(url==='/api/characters/components')return Promise.resolve(catalog);throw Error('Unexpected request '+url);},
  toast(){throw Error('Unexpected toast');}});
function load(file){vm.runInContext(fs.readFileSync(file,'utf8'),context,{filename:file});}
load(process.argv[5]);
load(process.argv[3]);
load(process.argv[4]);
(async()=>{
  await new Promise(resolve=>setImmediate(resolve));await new Promise(resolve=>setImmediate(resolve));
  const rows=document.getElementById('cp-rows').children;
  assert.deepEqual(rows.map(r=>r.children[1].textContent),
    ['newborn_lower','newborn_upper','head_01_male'], 'all unpublished components above published ones');
  const lower=rows[0].children[7].children[0];
  assert.equal(lower.attributes['aria-label'],'Atlas for newborn_lower');
  assert.deepEqual(lower.children.slice(1,3).map(o=>o.value),['15','14']);
  assert.equal(lower.dataset.cpAtlasRank,'1','current lower atlas is the second ranked option');
  const upper=rows[1].children[7].children[0];
  assert.deepEqual(upper.children.slice(1,4).map(o=>o.value),['30','31','32']);
  assert.equal(upper.dataset.cpAtlasRank,'1');
  const table=document.getElementById('cp-atlas-rows').children;
  const titles=table.filter(tr=>tr.className==='cp-atlas-family-row');
  assert.equal(titles.length,4,'atlas families have their own table headings');
  assert.deepEqual(titles.map(t=>t.children[0].textContent.split(' · ')[0]),
    ['head_01_male','newborn_boots','newborn_lower','newborn_upper']);
  const upperRows=table.filter(r=>r.children[0]?.textContent==='newborn_upper');
  assert.deepEqual(upperRows.map(r=>r.children[1].children[1].textContent),['512×512','256×256','128×128']);
  assert.deepEqual(upperRows.map(r=>r.children[1].children[0].className),
    ['cp-atlas-rank-dot cp-atlas-rank-0','cp-atlas-rank-dot cp-atlas-rank-1','cp-atlas-rank-dot cp-atlas-rank-2']);
  console.log('M198 atlas UI: prioritized part choices, ranks, grouped table, unpublished-first passed');
})().catch(err=>{console.error(err);process.exitCode=1;});
