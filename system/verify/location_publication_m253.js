/* M253: UI policy and registered atlas editor support first-time publication. */
const fs=require('node:fs');const vm=require('node:vm');const assert=require('node:assert/strict');
const root=require('node:path').resolve(__dirname,'../control-center/static');
const sandbox={window:{},console};vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(root+'/location-publication-state.js','utf8'),sandbox);
const plan=sandbox.window.game1LocationPublication.plan;
const atlas={id:38,filename:'bush_02_512x512_atlas.png',published_id:null,current:false,retired:false};
const item={atlasVariantId:38,atlasVariants:[atlas],model_path:'bush_02.fbx',model_sha256:'abc',
  model_published_sha256:'',model_asset_id:''};
let x=plan(item);assert.equal(x.count,2);assert.equal(x.atlasNeeded,true);assert.equal(x.modelNeeded,true);
assert.equal(x.reviewRequired,false);
const modelPublished={...item,model_asset_id:'123456',model_published_sha256:'abc'};
x=plan(modelPublished);assert.equal(x.count,1);assert.equal(x.modelNeeded,false);
x=plan({...modelPublished,atlasVariants:[{...atlas,published_id:'8888',current:true}]});
assert.equal(x.count,0);
x=plan({...modelPublished,atlasVariants:[{...atlas,published_id:'8888',current:false}]});
assert.equal(x.count,0);assert.equal(x.reviewRequired,true);
x=plan(modelPublished,[],true);assert.equal(x.count,2);
const html=fs.readFileSync(root+'/asset-atlas-editor.js','utf8');
assert.match(html,/data-ca-open-publish/);
assert.match(html,/onOpenPublish/);
console.log('M253 publication policy: 5 scenarios passed');
