// M454: independent MeshPart Atlas is a first-class publication resource.
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const path=require('node:path');
const root=path.resolve(__dirname,'../control-center/static');
const sandbox={window:{}};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(root,'location-publication-state.js'),'utf8'),sandbox);
const plan=sandbox.window.game1LocationPublication.plan;
const atlas=(id,image=null)=>({id,filename:'atlas_'+id+'.png',published_id:image,current:!!image,retired:false});
const catalog=[{variants:[atlas(71,'82028913618222'),atlas(85)]}];
const thuja={model_path:'thuja_02.fbx',model_asset_id:'83265019701312',model_sha256:'abc',
 model_published_sha256:'abc',appearanceMode:'material',meshOptions:{
   leaf_01:{appearanceMode:'material_atlas',atlasVariantId:71},
   thuja_02:{appearanceMode:'material_atlas',atlasVariantId:85}
 }};
let result=plan(thuja,catalog);
assert.equal(result.count,1);
assert.equal(result.modelNeeded,false);
assert.equal(result.atlasNeeded,false);
assert.equal(result.meshAtlases.length,1);
assert.equal(result.meshAtlases[0].id,85);
assert.deepEqual(Array.from(result.meshAtlases[0].meshNames),['thuja_02']);
const updatedCatalog=[{variants:[atlas(71,'82028913618222'),atlas(85,'998877665544')]}];
result=plan(thuja,updatedCatalog);
assert.equal(result.count,0);
assert.equal(result.meshAtlases.length,0);
result=plan({...thuja,meshOptions:{...thuja.meshOptions,
 branch:{appearanceMode:'material_atlas',atlasVariantId:85}}},catalog);
assert.equal(result.count,1,'shared variant must be published once');
assert.equal(result.meshAtlases[0].meshNames.length,2);
result=plan({...thuja,meshOptions:{branch:{appearanceMode:'material_atlas',atlasVariantId:999}}},catalog);
assert.equal(result.count,0);
assert.equal(result.unresolvedMeshAtlases.length,1,'missing variant must not be silently published');
const ui=fs.readFileSync(path.join(root,'location-asset-workflow.js'),'utf8');
assert.match(ui,/initial\.meshAtlases/);
assert.match(ui,/variants\/\$\{entry\.id\}\/publish/);
console.log('M454 MeshPart Atlas publication policy: 6 checks OK');
