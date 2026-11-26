"""View-only column preferences; sorted rows must never alter stable Database IDs."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[2]
STATIC=ROOT/'system/control-center/static'

class MonsterTableM559(unittest.TestCase):
    def test_ui_wiring(self):
        html=(STATIC/'index.html').read_text(encoding='utf8')
        js=(STATIC/'game-balance.js').read_text(encoding='utf8')
        self.assertLess(html.index('monster-table.js?v=559'),html.index('game-balance.js?v='))
        self.assertIn('window.game1MonsterTable.columns(fields[tab])',js)
        self.assertIn('window.game1MonsterTable.rows(d.monsters)',js)
        self.assertIn('window.game1MonsterTable.decorate(body.parentElement.tHead.rows[0],columns,render)',js)
        self.assertIn('balance:snapshot.balance,revision:snapshot.revision',js)

    @unittest.skipUnless(shutil.which('node'),'Node.js not installed')
    def test_view_order_numeric_text_boolean_and_storage_recovery(self):
        script=r'''
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const code=fs.readFileSync(process.argv[1],'utf8');
function create(prefs){
  const ctx={window:{},localStorage:{getItem:()=>JSON.stringify(prefs)}};
  vm.runInNewContext(code,ctx);
  return ctx.window.game1MonsterTable;
}
const defaults=['id','nameEn','hp','aggressive','deathChase'];
const data=[{id:'monster_001',nameEn:'Wolf',hp:100,aggressive:true},
{id:'monster_002',nameEn:'Toad',hp:9,aggressive:false},
{id:'monster_003',nameEn:'',hp:20,aggressive:true}];
const json=v=>JSON.parse(JSON.stringify(v));
const ids=v=>json(v.map(r=>r.id));
const original=JSON.stringify(data);
let view=create({order:['hp','id','hp','retired'],sortKey:'hp'});
assert.deepEqual(json(view.columns(defaults)),['hp','id','nameEn','aggressive','deathChase']);
assert.deepEqual(ids(view.rows(data)),['monster_002','monster_003','monster_001']);
view=create({sortKey:'hp',descending:true});view.columns(defaults);
assert.deepEqual(ids(view.rows(data)),['monster_001','monster_003','monster_002']);
view=create({sortKey:'nameEn',descending:true});view.columns(defaults);
assert.deepEqual(ids(view.rows(data)),['monster_001','monster_002','monster_003']);
view=create({sortKey:'aggressive'});view.columns(defaults);
assert.deepEqual(ids(view.rows(data)),['monster_002','monster_001','monster_003']);
view=create({sortKey:'retired',order:'invalid'});
assert.deepEqual(json(view.columns(defaults)),defaults);
assert.deepEqual(ids(view.rows(data)),ids(data));
assert.equal(JSON.stringify(data),original);
'''
        subprocess.run(['node','-e',script,str(STATIC/'monster-table.js')],check=True,capture_output=True,text=True)
