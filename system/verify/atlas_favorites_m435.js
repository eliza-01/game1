/* M435: cross-domain picker behavior, no browser or publication side effects. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '../control-center/static');
const window = {dispatchEvent: () => {}};
const context = vm.createContext({window, module: {exports:{}}, CustomEvent:class {constructor(type,options){this.type=type;this.detail=options.detail;}}, esc:s=>String(s), console});
for(const filename of ['atlas-identity.js', 'asset-atlas-editor.js', 'mesh-authoring.js','character-atlas-presentation.js']){
  vm.runInContext(fs.readFileSync(path.join(root, filename), 'utf8'), context, {filename});
}
const a = {id:1,atlas_key:'a',filename:'a_64x64_atlas.png',width:64,height:64,resolution:'64x64',published_id:'101',current:true,consumers:[{consumer_type:'location_asset'}]};
const b = {id:2,atlas_key:'b',filename:'b_64x64_atlas.png',width:64,height:64,resolution:'64x64',published_id:'102',current:true,consumers:[{consumer_type:'real_estate'}],favorite:true};
const c = {id:3,atlas_key:'c',filename:'c_64x64_atlas.png',width:64,height:64,resolution:'64x64',published_id:'103',current:true,consumers:[{consumer_type:'weapon'}]};
const catalog = [{atlasKey:'a',variants:[a]},{atlasKey:'b',variants:[b]},{atlasKey:'c',variants:[c]}];
const favorite = window.game1AtlasFavorites;
assert.equal(favorite.ordered([a,b,c])[0].id,2);
const editor = window.game1ConsumerAtlasEditor;
let sections = editor.sections([a,b,c]);
assert.equal(sections[0].key,'favorites');
assert.equal(sections[0].items.map(x=>x.id).join(','),'2');
assert.equal(sections[1].key,'location');
const html = editor.render({...editor.newState(),picker:true},{catalog});
assert.ok(html.indexOf('data-ca-attach="2"') < html.indexOf('data-ca-attach="1"'), 'shared modal must show favorites first');
const meshHTML = window.game1MeshAuthoring.atlasOptions(catalog);
assert.ok(meshHTML.indexOf('value="2"') < meshHTML.indexOf('value="1"'), 'MeshPart dropdown favorites first');
const character = window.game1CharacterAtlasPresentation.optionsForPart('a',catalog);
assert.equal(character[0].id,2,'favorite outranks character part matches');
assert.equal(character[1].id,1,'normal part matching priority remains');
favorite.update(2,false);
assert.equal(favorite.ordered([a,b,c])[0].id,1);
sections = editor.sections([a,b,c]);
assert.equal(sections.some(s=>s.key==='favorites'),false);
favorite.update(3,true);
assert.equal(editor.sections([a,b,c])[0].items[0].id,3);
console.log('M435 shared atlas favorite picker tests: OK');
