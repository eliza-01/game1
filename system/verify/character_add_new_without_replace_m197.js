// M197: exercise the real Inspect -> approval modal -> Register browser flow.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

class Element {
  constructor(tag = 'div') {
    this.tagName = tag;
    this.children = [];
    this.dataset = {};
    this.attributes = {};
    this.value = '';
    this.textContent = '';
    this.checked = false;
    this.disabled = false;
    this.parentElement = null;
    this.classList = { toggle() {} };
  }
  append(...children) {
    for (const child of children) {
      this.children.push(child);
      if (child && typeof child === 'object') child.parentElement = this;
    }
  }
  replaceChildren(...children) { this.children = []; this.append(...children); }
  setAttribute(key, value) { this.attributes[key] = value; }
  addEventListener() {}
  showModal() { this.open = true; }
  close() { this.open = false; }
  querySelectorAll(selector) {
    const found = [];
    const matches = node => {
      if (selector === 'input:checked') return node.tagName === 'input' && node.checked;
      if (selector === 'input') return node.tagName === 'input';
      if (selector === 'option') return node.tagName === 'option';
      if (selector === 'input[value^="rig:"]:checked')
        return node.tagName === 'input' && node.checked && node.value.startsWith('rig:');
      if (selector === '[data-cp-atlas-select]') return Object.hasOwn(node.dataset, 'cpAtlasSelect');
      const named = { '[data-rig-only]': 'rigOnly', '[data-mesh-approval]': 'meshApproval',
        '[data-partial-approval]': 'partialApproval', '[data-new-part]': 'newPart',
        '[data-rig-only]:checked': 'rigOnly', '[data-partial-approval]:checked': 'partialApproval' };
      return Object.hasOwn(named, selector) && Object.hasOwn(node.dataset, named[selector]) &&
        (!selector.endsWith(':checked') || node.checked);
    };
    const walk = node => {
      for (const child of node.children || []) {
        if (matches(child)) found.push(child);
        walk(child);
      }
    };
    walk(this);
    return found;
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
}

const elMap = new Map();
const document = {
  getElementById(id) { if (!elMap.has(id)) elMap.set(id, new Element()); return elMap.get(id); },
  createElement(tag) { return new Element(tag); },
  createTextNode(str) { const node = new Element('#text'); node.textContent = str; return node; },
  querySelectorAll() { return []; },
};
const el = name => document.getElementById('cp-' + name);
const old = ['head_01_male','newborn_boots','newborn_gloves','newborn_lower','newborn_upper'];
const row = (id,revision=1) => ({id,slot:id.split('_').at(-1),set_id:'',rig_id:'human',role:'part',
  triangles:1,existing_revision:revision,published_asset_id:revision?'asset_'+id:'',content_unchanged:false});
const oldRows = old.map(id=>row(id));
const hair = {...row('hair_03_common', 0),slot:'hair',attachment_mode:'pivot'};
const plan = {token:'token', rig_id:'human',bone_count:77,parts:[hair,...oldRows],
  conflicts:oldRows, registered:oldRows, new_sets:[],partial_required:false,rig_only_required:false,
  rig:{id:'human',changed:false}};
let registeredPayload = null;
let catalog={items:[],atlas_families:[],sets:[]};
const requests=[];
function request(url, options) {
  requests.push(url);
  if (url === '/api/characters/components' && !options) return Promise.resolve(catalog);
  if (url === '/api/files/choose-character-model') return Promise.resolve({path:'C:/fbx/human.fbx'});
  if (url === '/api/characters/components/inspect') return Promise.resolve(plan);
  if (url === '/api/characters/components/register') {
    registeredPayload=JSON.parse(options.body);
    catalog={items:[{id:'hair_03_common',kind:'part',slot:'hair',rig_id:'human',revision:1,
      published_revision:0,model_asset_id:'',status:'registered'},...oldRows.map(r=>({...r,kind:'part',
      revision:1,published_revision:1,model_asset_id:r.published_asset_id,status:'published'}))],atlas_families:[]};
    return Promise.resolve(catalog);
  }
  throw Error('Unexpected request ' + url);
}
const window = {
  game1CharacterPublications:{configure(){},selectionCell(){return new Element('td');},
    button(){return new Element('button');},setBusy(){},isRunning(){return false;}},
  game1CharacterComponentSummary:{render(){}},addEventListener(){},dispatchEvent(){},
};
window.game1CharacterAtlasPresentation=require(process.argv[3]);
const context=vm.createContext({document,window,request,Event:class Event {},
  Option: function Option(_label,value){const opt=new Element('option');opt.value=value;return opt;},
  toast(message){throw Error('Unexpected toast ' + message);}});
vm.runInContext(fs.readFileSync(process.argv[2],'utf8'),context,{filename:'character-components.js'});
const settle=async()=>{for(let i=0;i<6;i++)await new Promise(resolve=>setImmediate(resolve));};
(async()=>{
  await settle();
  el('choose').onclick();
  await settle();
  assert.equal(el('conflict').open,true,'Inspect opens review dialog');
  const newChecks=el('conflicts').querySelectorAll('[data-new-part]');
  const replaceChecks=el('conflicts').querySelectorAll('[data-mesh-approval]');
  assert.equal(newChecks.length,1,'new hair appears in review');
  assert.equal(newChecks[0].value,'hair_03_common');
  assert(newChecks[0].checked,'new hair selected by default');
  assert.equal(replaceChecks.length,5,'old parts appear separately');
  assert(replaceChecks.every(c=>!c.checked),'none of the old parts is selected');
  assert(!el('confirm').disabled,'new component alone is enough to confirm');
  newChecks[0].checked=false;
  newChecks[0].onchange();
  assert(el('confirm').disabled,'no operation selected -> confirmation disabled');
  newChecks[0].checked=true;
  newChecks[0].onchange();
  assert(!el('confirm').disabled);
  el('confirm').onclick();
  await settle();
  await settle();
  assert(registeredPayload,'Register posted request');
  assert.equal(registeredPayload.token,'token');
  assert.equal(JSON.stringify(registeredPayload.newParts),JSON.stringify(['hair_03_common']));
  assert.equal(JSON.stringify(registeredPayload.replacements),JSON.stringify([]));
  assert.equal(registeredPayload.replaceRig,false);
  assert.equal(registeredPayload.rigOnly,false);
  assert(requests.includes('/api/characters/components/register'));
  assert.match(el('status').textContent,/Registration complete/);
  console.log('M197 UI: new hair only, 5 untouched replacements, selection and register passed');
})().catch(err=>{console.error(err);process.exitCode=1;});
