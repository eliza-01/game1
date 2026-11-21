/* M400 · one Model appearance editor, shared grouped Atlas Registry, two modes. */
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const root=path.resolve(__dirname,'..','..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');
const context={window:{},esc:v=>String(v).replace(/&/g,'&amp;').replace(/</g,'&lt;')};
vm.createContext(context);
vm.runInContext(read('system/control-center/static/asset-atlas-editor.js'),context);
vm.runInContext(read('system/control-center/static/mesh-authoring.js'),context);
const author=context.window.game1MeshAuthoring;
const families=[
 {atlasKey:'loc_lamp',variants:[{id:11,filename:'lamp.png',current:true,published_id:'101',consumers:[{consumer_type:'location_asset'}]}]},
 {atlasKey:'estate_roof',variants:[{id:22,filename:'roof.png',current:true,published_id:'202',consumers:[{consumer_type:'real_estate'}]}]},
 {atlasKey:'npc_skin',variants:[{id:33,filename:'skin.png',current:true,published_id:'303',consumers:[{consumer_type:'npc'}]}]},
 {atlasKey:'shared',variants:[{id:44,filename:'shared.png',current:true,published_id:'404'}]},
];
const analysis={meshes:[{name:'body',vertices:12,bones:[]},{name:'leaf',vertices:20,bones:[]},
 {name:'rig_carrier',vertices:0,bones:[]}]};
const opts={body:{appearanceMode:'atlas',visualMaterial:'Concrete',visualColor:'#CACACA',atlasVariantId:22},
 leaf:{appearanceMode:'material',visualMaterial:'Plastic',visualColor:'#FFFFFF'}};
const html=author.inspectionView(analysis,opts,'location-mesh',{
 atlases:families,materials:[{id:'Plastic',label:'Plastic'},{id:'SmoothPlastic',label:'SmoothPlastic'},{id:'Concrete',label:'Concrete'}],
 defaultUsesAtlas:true,alphaEnabled:false,
});
assert.match(html,/Material \+ Color \+ Atlas/);
assert.match(html,/Material \+ Color/);
assert.doesNotMatch(html,/<option value="atlas"/);
for(const label of ['Location Assets','Real Estate','NPC','Shared \/ unused'])assert.ok(html.includes(`label="${label}"`),label);
for(const name of ['loc_lamp','estate_roof','npc_skin','shared'])assert.ok(html.includes(name),name);
assert.match(html,/value="22" selected/);
assert.ok(!html.includes('data-mesh-appearance')||html.indexOf('data-mesh-appearance',html.indexOf('rig_carrier'))===-1);
const seeded=author.seeded(analysis,opts);
assert.equal(seeded.body.appearanceMode,'material_atlas');
assert.equal(seeded.body.atlasVariantId,22);
assert.equal(seeded.body.visualMaterial,'Concrete');
assert.equal(seeded.rig_carrier,undefined);
assert.equal(author.displayAppearanceMode('atlas'),'material_atlas');
const workflow=read('system/control-center/static/location-asset-workflow.js');
assert.ok(workflow.includes('data-la-model-appearance-mode'));
assert.ok(workflow.includes('game1ConsumerAtlasEditor.render'));
assert.ok(workflow.includes('game1ConsumerAtlasEditor.wire'));
assert.ok(!workflow.includes("{id:'atlas',label:'Texture · atlas'}"));
assert.ok(workflow.includes('data-la-model-alpha'));
const index=read('system/control-center/static/index.html');
assert.ok(!index.includes('<option value="atlas">Texture Atlas · PNG/JPG</option>'));
const estate=read('system/control-center/static/real-estate.js');
assert.ok(!estate.includes('<option value="atlas"'));
assert.ok(estate.includes("'material_atlas'"));
console.log('M400 UI · shared grouped atlas selection and 2-mode authoring OK');
