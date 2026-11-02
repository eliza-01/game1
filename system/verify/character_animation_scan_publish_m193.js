// M193: run the actual Character Animations Scan Folder UI in a minimal DOM.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

class Element {
  constructor(id = '') {
    this.id = id;
    this.disabled = false;
    this.value = '';
    this.checked = false;
    this.dataset = {};
    this.open = false;
    this.textContent = '';
    this.listeners = {};
    this.children = [];
    this._html = '';
  }
  set innerHTML(html) {
    this._html = html;
    if (this.id === 'animation-scan-review') {
      this.children = [...html.matchAll(/<input type="checkbox" data-review-index="(\d+)" (checked|disabled)>/g)]
        .map((match) => {
          const child = new Element();
          child.dataset.reviewIndex = match[1];
          child.checked = match[2] === 'checked';
          child.disabled = match[2] === 'disabled';
          return child;
        });
    }
  }
  get innerHTML() { return this._html; }
  querySelectorAll(selector) {
    if (selector === '[data-review-index]:checked') return this.children.filter(child => child.checked);
    return [];
  }
  addEventListener(name, callback) { (this.listeners[name] ||= []).push(callback); }
  fire(name) { for (const callback of this.listeners[name] || []) callback({ target: this }); }
  showModal() { this.open = true; }
  close() { this.open = false; }
}
const elements = new Map();
const el = id => {
  if (!elements.has(id)) elements.set(id, new Element(id));
  return elements.get(id);
};
const document = {getElementById: el, querySelectorAll: () => []};
const window = {};
const state = { animationCharacter: 'human_male', animationFolder: 'C:/animations' };
const calls = [];
const notices = [];
let pendingPreview = null;
let registerFailure = false;
let loadCount = 0;
const preview = (characterId = state.animationCharacter, selected = [true, true]) => ({
  characterId, filesScanned: 2, rootPath: 'C:/animations', unassigned: [],
  items: selected.map((selectable, index) => ({
    filename: 'clip' + index + '.rbxm', path: '/clip' + index, sha256: 'hash' + index,
    status: selectable ? 'NEW' : 'UNCHANGED', selectable,
    scope: 'base', slot: 'idle', variant: index + 1,
  })),
});
const callbacks = {
  state: () => state,
  render() { /* Importantly: main render() never re-renders the scan modal. */ },
  async load() { loadCount++; },
  toast(message, error) { notices.push({ message, error }); },
  request(path, args) {
    calls.push({ path, args });
    if (path === '/api/animations/preview')
      return new Promise((resolve, reject) => { pendingPreview = { resolve, reject }; });
    if (path === '/api/animations/register-selected') {
      if (registerFailure) return Promise.reject(Error('register failed'));
      const items = JSON.parse(args.body).items;
      return Promise.resolve({ count: items.length, registered: items.map((item, i) => ({ clipId: 'clip-' + i })) });
    }
    if (/\/api\/animations\/clip-\d+\/publish/.test(path)) return Promise.resolve({ ok: true });
    throw Error('unexpected API path: ' + path);
  },
};
const context = vm.createContext({ window, document, localStorage: {getItem: () => null}, console });
vm.runInContext(fs.readFileSync(process.argv[2], 'utf8'), context, { filename: 'character-animation-ui.js' });
window.game1AnimationUI.init(callbacks);
el('animation-folder-path').value = 'C:/animations';
const button = el('animation-register-selected');
const tick = () => new Promise(resolve => setImmediate(resolve));
const flush = async () => { for (let i = 0; i < 5; ++i) await tick(); };

(async () => {
  // While the preview request is running, publication must be disabled.
  let operation = window.game1AnimationUI.scanFolder();
  assert.equal(button.disabled, true);
  pendingPreview.resolve(preview());
  await operation;
  assert.equal(el('animation-scan-dialog').open, true);
  assert.equal(button.disabled, false, 'selectable NEW files must unlock Register + Publish after scan');
  const review = el('animation-scan-review');
  for (const checkbox of review.children) checkbox.checked = false;
  review.fire('change');
  assert.equal(button.disabled, true, 'unchecked selection cannot publish');
  review.children[1].checked = true;
  review.fire('change');
  assert.equal(button.disabled, false, 'checking a selectable file re-enables publish');

  // Failed registration should permit retry with the same selected files.
  registerFailure = true;
  await button.onclick();
  assert.equal(button.disabled, false, 'failed registration unlocks retry');
  assert.equal(notices.at(-1).message, 'register failed');
  registerFailure = false;
  await button.onclick();
  assert.equal(button.disabled, true, 'committed registration cannot be submitted twice');
  assert.equal(loadCount, 1);
  const registrations = calls.filter(call => call.path === '/api/animations/register-selected');
  assert.equal(registrations.length, 2);
  assert.equal(JSON.parse(registrations[1].args.body).items.length, 1, 'only checked clip registered');
  assert.equal(calls.filter(call => call.path.includes('/publish')).length, 1);

  // An empty preview must not allow registration.
  operation = window.game1AnimationUI.scanFolder();
  pendingPreview.resolve(preview('human_male', [false, false]));
  await operation;
  assert.equal(button.disabled, true, 'no selectable files');

  // Switching character while reviewing must reject the stale scan.
  operation = window.game1AnimationUI.scanFolder();
  pendingPreview.resolve(preview('human_male', [true]));
  await operation;
  assert.equal(button.disabled, false);
  state.animationCharacter = 'human_female';
  review.fire('change');
  assert.equal(button.disabled, true, 'selection for another character must be disabled');
  await button.onclick();
  assert.equal(calls.filter(call => call.path === '/api/animations/register-selected').length, 2);

  // If character changes before preview resolves, discard that response entirely.
  state.animationCharacter = 'human_male';
  operation = window.game1AnimationUI.scanFolder();
  state.animationCharacter = 'human_female';
  pendingPreview.resolve(preview('human_male', [true]));
  await operation;
  assert.equal(button.disabled, true);
  assert.match(notices.at(-1).message, /изменился/);

  // A fresh scan for the new character is immediately publishable.
  operation = window.game1AnimationUI.scanFolder();
  pendingPreview.resolve(preview('human_female', [true]));
  await operation;
  assert.equal(button.disabled, false);
  await button.onclick();
  assert.equal(calls.filter(call => call.path === '/api/animations/register-selected').length, 3);
  assert.equal(button.disabled, true);
  console.log('M193 Character Animations: preview, selection, retry, stale character, registration and publish passed');
})().catch(error => {console.error(error); process.exitCode = 1;});
