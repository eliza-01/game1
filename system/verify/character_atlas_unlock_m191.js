// Run with Node.js. Exercises the actual Character Components UI code in a minimal DOM.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

class Element {
  constructor(tag = 'div') {
    this.tagName = tag;
    this.children = [];
    this.dataset = {};
    this.attributes = {};
    this.parentElement = null;
    this.value = '';
    this.textContent = '';
    this.disabled = false;
    this.classList = { toggle() {} };
  }
  append(...children) {
    for (const child of children) {
      this.children.push(child);
      if (child && typeof child === 'object') child.parentElement = this;
    }
  }
  replaceChildren(...children) { this.children = []; this.append(...children); }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  addEventListener() {}
  querySelectorAll(selector) {
    const matched = [];
    const match = node => (selector === 'select' && node.tagName === 'select') ||
      (selector === '[data-cp-atlas-select]' && Object.hasOwn(node.dataset, 'cpAtlasSelect'));
    const walk = node => {
      for (const child of node.children) {
        if (match(child)) matched.push(child);
        walk(child);
      }
    };
    walk(this);
    return matched;
  }
  querySelector(selector) {
    if (selector === 'option') return this.children.find(child => child.tagName === 'option') || null;
    return this.querySelectorAll(selector)[0] || null;
  }
}

const elements = new Map();
const document = {
  getElementById(id) {
    if (!elements.has(id)) elements.set(id, new Element());
    return elements.get(id);
  },
  createElement(tag) { return new Element(tag); },
  querySelectorAll(selector) { return selector === '[data-cp-sort]' ? [] : []; },
};
const events = new Map();
let publishing = false;
let uiBusy = false;
let pending = null;
let atlasCalls = 0;
let catalog = {
  items: [
    {id: 'upper', kind: 'part', slot: 'upper', rig_id: 'human', status: 'published', revision: 1, published_revision: 1,
      model_asset_id: '100', atlas: {variant_id: 1, revision: 3, current: true}},
    {id: 'lower', kind: 'part', slot: 'lower', rig_id: 'human', status: 'published', revision: 1, published_revision: 1,
      model_asset_id: '200', atlas: {variant_id: 2, revision: 4, current: true}},
  ],
  atlas_families: [{atlasKey: 'character', variants: [
    {id: 1, width: 1024, height: 1024, current: true},
    {id: 2, width: 512, height: 512, current: true},
    {id: 3, width: 256, height: 256, current: true},
  ]}],
};
const deepClone = obj => JSON.parse(JSON.stringify(obj));
const window = {
  game1CharacterPublications: {
    configure() {},
    selectionCell() { return new Element('td'); },
    button() { return new Element('button'); },
    setBusy(value) { uiBusy = value; },
    isRunning() { return publishing; },
  },
  game1CharacterComponentSummary: { render() {} },
  addEventListener(name, fn) {
    if (!events.has(name)) events.set(name, []);
    events.get(name).push(fn);
  },
  dispatchEvent(event) { for (const fn of events.get(event.type) || []) fn(event); },
};
const request = (url, options) => {
  if (url === '/api/characters/components' && !options) return Promise.resolve(deepClone(catalog));
  if (url === '/api/characters/components/atlas' && options) {
    atlasCalls++;
    const payload = JSON.parse(options.body);
    return new Promise((resolve, reject) => { pending = { payload, resolve, reject }; });
  }
  throw new Error(`unexpected API request: ${url}`);
};
const context = vm.createContext({
  window, document, request,
  Option: function Option(label, value) { const node = new Element('option'); node.textContent = label; node.value = String(value); return node; },
  Event: class Event { constructor(type) { this.type = type; } },
  toast(message) { throw Error('unexpected toast: ' + message); },
});
vm.runInContext(fs.readFileSync(process.argv[2], 'utf8'), context, { filename: 'character-components.js' });
const rows = () => document.getElementById('cp-rows').querySelectorAll('select');
const row = id => rows().find(node => node.attributes['aria-label'] === 'Atlas for ' + id);
const tick = () => new Promise(resolve => setImmediate(resolve));
const settled = async () => { for (let i = 0; i < 4; i++) await tick(); };

(async () => {
  await settled();
  assert.equal(rows().length, 2, 'initial component rows are rendered');
  assert(rows().every(node => !node.disabled), 'initial row selectors are enabled');
  const original = row('upper');
  original.value = '3';
  original.onchange();
  assert.equal(atlasCalls, 1);
  assert.equal(uiBusy, true);
  assert(rows().every(node => node.disabled), 'all selectors locked while network is busy');
  catalog.items[0].atlas = {variant_id: 3, revision: 4, current: true};
  pending.resolve({ok: true});
  await settled();
  assert.equal(uiBusy, false, 'network busy is reset');
  assert.notEqual(row('upper'), original, 'successful refresh replaces the DOM row');
  assert(rows().every(node => !node.disabled), 'all NEW selectors are unlocked after successful refresh');
  assert.equal(String(row('upper').value), '3', 'the selected atlas is shown');
  assert.match(document.getElementById('cp-status').textContent, /Atlas selected/);

  // Rebind a second component immediately, without a page reload.
  const second = row('lower');
  second.value = '1';
  second.onchange();
  assert.equal(atlasCalls, 2);
  catalog.items[1].atlas = {variant_id: 1, revision: 5, current: true};
  pending.resolve({ok: true});
  await settled();
  assert(rows().every(node => !node.disabled));
  assert.equal(String(row('lower').value), '1');

  // Failed POST must also unlock dropdowns so the user can retry.
  row('upper').value = '2';
  row('upper').onchange();
  assert(rows().every(node => node.disabled));
  pending.reject(new Error('backend unavailable'));
  await settled();
  assert(rows().every(node => !node.disabled), 'failure must unlock selectors');
  assert.match(document.getElementById('cp-status').textContent, /backend unavailable/);

  // Queue events are a separate lock source. Do not unlock during publication.
  publishing = true;
  window.dispatchEvent(new context.Event('character-publication-state'));
  assert(rows().every(node => node.disabled), 'queue running locks atlas selectors');
  publishing = false;
  window.dispatchEvent(new context.Event('character-publication-state'));
  assert(rows().every(node => !node.disabled), 'queue completion unlocks atlas selectors');
  console.log('Character Shared Atlas UI: success, repeat, failure and queue transitions passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
