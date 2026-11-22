/* UI contract: create-only names, default visual options, existing revisions unchanged. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const root=path.join(__dirname,'../control-center/static');
const window={game1ConsumerAtlasEditor:{sections:()=>[]}};
const ctx={window,esc:value=>String(value),console};
vm.createContext(ctx);
for(const file of ['asset-name-defaults.js','mesh-authoring.js'])
  vm.runInContext(fs.readFileSync(path.join(root,file),'utf8'),ctx,{filename:file});
const names=window.game1AssetNameDefaults;
assert.equal(names.title('  dark_OAK-tree 02  '),'Dark Oak Tree 02');
assert.equal(names.fromPath('C:\\assets\\night_WOLF.fbx'),'Night Wolf');
assert.equal(names.fromPath('/tmp/СТАРЫЙ_ДУБ.FBX'),'Старый Дуб');
const field={value:''};let synced=0;
assert.equal(names.fillFromPath(field,'forest_guard_01.fbx',()=>synced++,true),true);
assert.equal(field.value,'Forest Guard 01');
assert.equal(synced,1);
assert.equal(names.fillFromPath(field,'other.fbx',()=>synced++,true),false);
assert.equal(field.value,'Forest Guard 01');
assert.equal(names.fillFromPath({value:''},'other.fbx',null,false),false);
const mesh=window.game1MeshAuthoring;
const analysis={meshes:[{name:'rig_carrier'},{name:'Stone'},{name:'COL_legacy'},{name:'Glass'}]};
const created=mesh.seeded(analysis,{},true);
assert.deepEqual(Object.keys(created),['Stone','Glass']);
assert.equal(created.Stone.noCollide,true);
assert.equal(created.Stone.appearanceMode,'material_atlas');
assert.equal(created.Stone.visualMaterial,'Plastic');
assert.equal(created.Glass.noCollide,true);
const existing=mesh.seeded(analysis,{});
assert.equal(existing.Stone.noCollide,false); // no retroactive collision migration
assert.equal(Object.hasOwn(existing.Stone,'appearanceMode'),false);
const override=mesh.seeded(analysis,{Stone:{noCollide:false,appearanceMode:'material'}},true);
assert.equal(override.Stone.noCollide,false);
assert.equal(override.Stone.appearanceMode,'material');
assert.equal(mesh.defaults('roof').noCollide,true); // existing House behavior
const generated=fs.readFileSync(path.join(root,'index.html'),'utf8');
assert(generated.indexOf('asset-name-defaults.js')<generated.indexOf('character-assets.js'));
for(const script of ['deco-assets.js','weapon-assets.js','arrow-assets.js','npc-assets.js','monster-assets.js']) {
  assert(fs.readFileSync(path.join(root,script),'utf8').includes('game1AssetNameDefaults.'),script);
}
console.log('M437 create-only naming and per-mesh defaults: OK');
