/* M285: manual timeline entry remains possible when the Studio clip preview fails. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
const clipId = 'human_female__weapon__hands__attack__01';
const elements = new Map();
function element() {
  const e = {value: '', disabled: false, dataset: {}, html: '', text: '', style: {},
    className: '', controls: {}, classList: {add(){},remove(){}}, onclick: null, onchange: null,
    querySelectorAll(selector) {
      if (selector !== '[data-timeline-event]') return [];
      if (this.controls[selector]) return this.controls[selector];
      return this.controls[selector] = [...this.html.matchAll(/data-timeline-event="([^"]+)"/g)].map(m => {
        const input = element(); input.dataset.timelineEvent = m[1];
        return input;
      });
    },
    set innerHTML(value) {this.html=value;this.controls={};}, get innerHTML() {return this.html;},
    set textContent(value) {this.text=value;}, get textContent() {return this.text;},
  };
  return e;
}
function $(id) { if (!elements.has(id)) elements.set(id, element()); return elements.get(id); }
const row = {subjectType:'characters',subjectId:'human_female',clipId,
  clipName:'hands_attack_01',subjectName:'Human Female',weaponSet:'hands',
  duration:0,events:{},configured:false,modelAssetId:'134874851448365',
  animationAssetId:'82219458610259'};
const snapshot = {items:[row],subjects:{characters:[{id:'human_female',name:'Human Female'}]},
  eventCatalogs:{characters:[{name:'HitStart'},{name:'HitEnd'}]}};
let saved;
const context = vm.createContext({window:{},document:{activeElement:null},$,esc:String,
  toast(){},setInterval,clearInterval,console,
  request: async (url, options) => {
    if (url === '/api/timelines/save') { saved = JSON.parse(options.body); return snapshot; }
    if (url === '/api/timelines') return snapshot;
    throw Error(`unexpected URL ${url}`);
  }});
vm.runInContext(fs.readFileSync(path.join(root,'system/control-center/static/timelines.js'),'utf8'), context);
async function main() {
  context.window.game1TimelinesSelectAttack('human_female',clipId);
  await context.window.game1TimelinesLoad();
  assert.equal($('timeline-save').disabled, true, 'no fake events or duration');
  $('timeline-duration-input').value='1.875';
  $('timeline-duration-input').onchange();
  assert.equal($('timeline-save').disabled, true, 'duration alone is not enough');
  for (const [name, value] of [['HitStart','32.5'],['HitEnd','55']]) {
    const input = $('timeline-events').querySelectorAll('[data-timeline-event]').find(e => e.dataset.timelineEvent===name);
    assert.equal(typeof input.onchange,'function');
    input.value=value;
    input.onchange();
  }
  assert.equal($('timeline-save').disabled,false,'complete validated timeline can be saved');
  $('timeline-save').onclick();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(saved.clipId,clipId);
  assert.equal(saved.duration,1.875);
  assert.equal(saved.events.HitStart.normalizedTime,0.325);
  assert.equal(saved.events.HitEnd.normalizedTime,0.55);
  console.log('M285 manual timeline authoring: OK');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
