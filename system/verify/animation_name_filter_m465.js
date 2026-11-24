'use strict';
// UI integration with the real animation renderer; no browser dependencies.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '..', 'control-center', 'static');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
assert.match(html, /id="animation-name-search"[^>]*type="search"|id="animation-name-search" type="search"/);
const controls = new Map();
function get(id) {
  if (!controls.has(id)) controls.set(id, {
    value:'', checked:true, textContent:'', children:[], dataset:{},
    replaceChildren(){this.children=[];}, append(el){this.children.push(el);},
    addEventListener(name, fn){this[name]=fn;},
    querySelectorAll(){return []},
  });
  return controls.get(id);
}
const window = {};
const document = {
  getElementById:get,
  querySelectorAll:()=>[],
  createElement:()=>({dataset:{},innerHTML:'',className:''}),
};
const context = {window,document,localStorage:{getItem:()=> '1',setItem(){}}, console};
vm.runInNewContext(fs.readFileSync(path.join(root,'character-animation-ui.js'),'utf8'),context);
const state = {animationFilter:'all',animations:{items:[],filenameRules:[
  {scope:'social',context:'social',state:'clap',canonicalFilename:'human_male_social_clap.rbxm'},
  {scope:'social',context:'social',state:'sad',canonicalFilename:'human_male_social_sad.rbxm'},
  {scope:'base',context:'base',state:'idle',canonicalFilename:'human_male_base_idle.rbxm'},
]}};
window.game1AnimationUI.init({state:()=>state,render:()=>window.game1AnimationUI.renderRows()});
const rows=()=>get('animation-rows').children;
window.game1AnimationUI.renderRows();
assert.equal(rows().length,3);
get('animation-name-search').value='CLAP';
get('animation-name-search').input();
assert.equal(rows().length,1);
assert.equal(rows()[0].dataset.slot,'clap');
state.animationFilter='base';
window.game1AnimationUI.renderRows();
assert.equal(rows().length,0,'search must respect section filter');
state.animationFilter='social';
window.game1AnimationUI.renderRows();
assert.equal(rows().length,1);
get('animation-name-search').value='sad';
get('animation-name-search').input();
assert.equal(rows()[0].dataset.slot,'sad');
get('animation-name-search').keydown({key:'Escape'});
assert.equal(get('animation-name-search').value,'');
assert.equal(rows().length,2);
console.log('m465 animation search: ok');
