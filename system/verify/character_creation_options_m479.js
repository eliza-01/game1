// M479 UI smoke: five exact authored views and update payload without clobber.
const fs=require('fs'), vm=require('vm'), assert=require('assert');
const path=require('path');
const script=fs.readFileSync(path.resolve(__dirname,'../control-center/static/character-creation-options.js'),'utf8');
// Existing projects receive this section on OptionsStore startup; the source
// snapshot need not already contain the migrated field.
const loaded=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../../assets/manifests/options.json'),'utf8')).characterCreation;
const defaultViews=['SelectionOverview','MaleFullBody','FemaleFullBody','MaleFace','FemaleFace'];
const settings=loaded||{enabled:false,useStudioAnchors:true,transitionSeconds:0.9,
  faceTransitionSeconds:0.65,desktopPanelWidthPx:340,mobilePanelWidthPx:290,
  views:Object.fromEntries(defaultViews.map(key=>[key,{cframe:[0,0,0,1,0,0,0,1,0,0,0,1],fov:70}]))};
const elements=new Map();
function node(id){
  if(!elements.has(id)) elements.set(id,{id,value:'',checked:false,onclick:null,innerHTML:''});
  return elements.get(id);
}
let saved;
const context={
 document:{getElementById:node},
 game1OptionsSave(payload){saved=payload},
 toast(message,err){throw new Error(message)},
};
vm.createContext(context);vm.runInContext(script,context);
vm.runInContext('game1CreationOptionsRender(input)',Object.assign(context,{input:settings}));
const order=['SelectionOverview','MaleFullBody','FemaleFullBody','MaleFace','FemaleFace'];
const html=node('option-creation-views').innerHTML;
let last=-1;
for(const key of order){const pos=html.indexOf(key);assert(pos>last, key);last=pos;}
for(const key of order){
  // Simulate DOM hydration of HTML input markup in this no-browser test.
  const src=settings.views[key];
  node('option-creation-cf-'+key).value=src.cframe.join(', ');
  node('option-creation-fov-'+key).value=String(src.fov);
  assert.equal(node('option-creation-cf-'+key).value,src.cframe.join(', '));
  assert.equal(node('option-creation-fov-'+key).value,'70');
}
node('option-creation-enabled').checked=true;
node('option-creation-transition').value='1.25';
node('option-creation-save').onclick();
assert(saved.characterCreation.enabled);
assert.equal(saved.characterCreation.transitionSeconds,1.25);
assert.deepStrictEqual(Object.keys(saved.characterCreation.views),order);
assert.equal(saved.characterCreation.views.FemaleFace.cframe.length,12);
const faceMaterials=['Plastic','Slate','Fabric','SmoothPlastic','Sandstone','Grass','LeafyGrass','Concrete'];
for(const group of ['hair','eyes','eyebrows','head']){
  assert.equal(node('option-creation-materials-'+group).value,faceMaterials.join(', '));
  assert.equal(JSON.stringify(saved.characterCreation.materialChoices[group]),JSON.stringify(faceMaterials));
}
assert.equal(saved.characterCreation.animations.chancePercent,settings.animations?.chancePercent??35);
assert.equal(saved.characterCreation.animations.weights.bow,settings.animations?.weights?.bow??100);
node('option-creation-animation-chance').value='75';
node('option-creation-animation-unaware').value='0';
node('option-creation-save').onclick();
assert.equal(saved.characterCreation.animations.chancePercent,75);
assert.equal(saved.characterCreation.animations.weights.unaware,0);
console.log('m479 character creation options ui passed');
