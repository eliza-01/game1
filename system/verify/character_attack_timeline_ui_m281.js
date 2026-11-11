/* M281 regression: published != hit-timing-ready; Animations links to exact timeline. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
const clipId = 'human_female__weapon__hands__attack__01';

function element() {
  return {
    children: [], controls: {}, dataset: {}, className: '', value: '', checked: false,
    classList: {toggle() {}, add() {}, remove() {}},
    setAttribute() {}, addEventListener() {},
    append(...items) { this.children.push(...items); },
    replaceChildren(...items) { this.children = [...items]; },
    querySelector(selector) {
      if (!this.controls[selector]) this.controls[selector] = {
        handlers: {}, addEventListener(event, callback) {this.handlers[event] = callback;},
        onchange: null, onclick: null,
      };
      return this.controls[selector];
    },
    querySelectorAll() {return [];},
    set innerHTML(value) {this.html = value;},
    get innerHTML() {return this.html || '';},
    set textContent(value) {this.text = value;},
    get textContent() {return this.text || '';},
  };
}
function harness() {
  const nodes = new Map();
  const $ = id => { if (!nodes.has(id)) nodes.set(id, element()); return nodes.get(id); };
  const document = {getElementById: $, createElement: element, querySelectorAll() {return [];}};
  const window = {};
  const sandbox = {window, document, $, console,
    localStorage: {getItem() {return null;}, setItem() {}},
    esc: String, toast() {}, setInterval, clearInterval, request: async () => ({}),
  };
  return {nodes, $, window, sandbox};
}
async function main() {
  const u = harness();
  vm.runInNewContext(fs.readFileSync(path.join(root, 'system/control-center/static/character-animation-ui.js'), 'utf8'), u.sandbox);
  const row = {clip_id: clipId, scope: 'weapon', weapon_set: 'hands', slot: 'attack', variant: 1,
    name: 'hands_attack_01', asset_id: '82219458610259', status: 'PUBLISHED', weight: 100,
    binding_id: 'binding__human_female__weapon__hands__attack__01'};
  const state = {animations: {items: [row]}, animationFilter: 'all', animationSelected: ''};
  let timelineConfigured = false;
  let opened = '';
  u.window.game1AnimationUI.init({
    state: () => state,
    request: async () => ({items: [{clipId, configured: timelineConfigured}]}),
    render() {}, openTimeline: id => {opened = id;},
  });
  u.window.game1AnimationUI.renderRows();
  assert.match(u.$('animation-rows').children[0].innerHTML, /PUBLISHED/);
  await u.window.game1AnimationUI.refreshAttackTimelines();
  const pending = u.$('animation-rows').children[0];
  assert.match(pending.innerHTML, /таймлайн: нужен HitStart \/ HitEnd/);
  pending.querySelector('[data-timeline]').handlers.click();
  assert.equal(opened, clipId, 'timeline link must carry canonical clip ID, not filename');
  timelineConfigured = true;
  await u.window.game1AnimationUI.refreshAttackTimelines();
  assert.match(u.$('animation-rows').children[0].innerHTML, /таймлайн: готов/);

  const t = harness();
  t.sandbox.request = async () => ({
    items: [{subjectType: 'characters', subjectId: 'human_female', clipId,
      clipName: 'hands_attack_01', subjectName: 'Human Female', weaponSet: 'hands',
      configured: false, duration: 0, events: {}, modelAssetId: '134874851448365',
      animationAssetId: '82219458610259'}],
    subjects: {characters: [{id: 'human_female', name: 'Human Female'}]},
    eventCatalogs: {characters: [{name: 'HitStart'}, {name: 'HitEnd'}]},
  });
  vm.runInNewContext(fs.readFileSync(path.join(root, 'system/control-center/static/timelines.js'), 'utf8'), t.sandbox);
  t.window.game1TimelinesSelectAttack('human_female', clipId);
  await t.window.game1TimelinesLoad();
  assert.equal(t.$('timeline-subject').value, 'human_female');
  assert.equal(t.$('timeline-clip-id').textContent, clipId);
  assert.match(t.$('timeline-status').innerHTML, /hit timing required/);
  console.log('M281 animation + timeline UI: OK');
}
main().catch(error => {console.error(error); process.exitCode = 1;});
