"""M75: first custom override and visible Studio Play control regression checks."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from animation_speed_scaling_store import AnimationSpeedScalingStore


class CustomScalingHotfixTests(unittest.TestCase):
    def test_existing_catalog_and_initially_missing_override_array(self):
        with tempfile.TemporaryDirectory(prefix='m75-catalog-') as temp:
            path = Path(temp)
            for name in ('character-animations.json', 'monster-animations.json', 'npc-animations.json'):
                target = path / 'assets/manifests' / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / 'assets/manifests' / name, target)
            store = AnimationSpeedScalingStore(path)
            snapshot = store.snapshot()
            self.assertNotIn('customScaling', snapshot)  # legacy profile before first override
            self.assertTrue({'character', 'monster', 'npc'} <= {item['kind'] for item in snapshot['catalog']})
            for item in snapshot['catalog']:
                self.assertTrue(item['assetId'].isdigit())

    def test_asset_manager_first_search_pick_and_cancel(self):
        # Execute the actual UI JavaScript with a small DOM stand-in if Node is present.
        # Python-only installations still exercise the static fallback checks below.
        js = (ROOT / 'system/control-center/static/animation-speed.js').read_text(encoding='utf-8')
        self.assertIn('animationSpeedState.data.customScaling=[]', js)
        self.assertIn('saved.push({assetId:aid', js)
        node = shutil.which('node')
        if not node:
            return
        script = r'''
const fs=require('fs'),vm=require('vm');
let chosen=[];
const ui={};
function elem(id){
  if(!ui[id]) ui[id]={value:'',innerHTML:'',hidden:false,onclick:null,oninput:null,querySelectorAll(selector){
    if(id==='custom-scaling-results'&&selector==='[data-custom-pick]'){
      const hits=[...this.innerHTML.matchAll(/data-custom-pick="([0-9]+)"/g)];
      chosen=hits.map(hit=>({dataset:{customPick:hit[1]},onclick:null}));
      return chosen;
    }
    return [];
  },querySelector(){return {scrollIntoView(){}}}};
  return ui[id];
}
const context={window:{},$:(id)=>elem(id),esc:v=>String(v),toast:()=>{},request:async()=>({}),console};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[2],'utf8'),context);
vm.runInContext(`animationSpeedState.data={profiles:[],catalog:[{assetId:'12345678',kind:'npc',name:'guard_attack_01',subject:'guard',channel:'attack'}]};customScalingRender()`,context);
ui['custom-scaling-search'].oninput({target:{value:'guard'}});
if(chosen.length!==1 || typeof chosen[0].onclick!=='function') throw Error('search result not clickable');
chosen[0].onclick();
const draft=vm.runInContext('animationSpeedState.data.customScaling',context);
if(draft.length!==1 || draft[0].assetId!=='12345678' || !draft[0]._draft) throw Error('first selection failed to persist in UI state');
if(!ui['custom-scaling-rows'].innerHTML.includes('guard_attack_01')) throw Error('selected animation not rendered');
console.log('M75 DOM first-pick passed');
'''
        with tempfile.TemporaryDirectory(prefix='m75-node-') as temp:
            harness = Path(temp) / 'harness.cjs'
            harness.write_text(script, encoding='utf-8')
            process = subprocess.run([node, str(harness), str(ROOT / 'system/control-center/static/animation-speed.js')], capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stdout + '\n' + process.stderr)

    def test_debug_button_not_offscreen_and_remote_nonblocking(self):
        client = (ROOT / 'src/client/dev/CustomScalingDebugController.luau').read_text(encoding='utf-8')
        self.assertNotIn('UDim2.fromOffset(16, 635)', client)
        self.assertIn('StudioDebugDock.ButtonPosition("CS")', client)
        self.assertIn('StudioDebugDock.WindowPosition("CS", 350)', client)
        self.assertIn('task.spawn(function()', client)
        self.assertIn('Game1DebugPanelOpen', client)
        self.assertIn('CS button visible', client)
        self.assertIn('CustomScaling service unavailable', client)

if __name__ == '__main__':
    unittest.main()
