"""Studio debug dock and Weapon Registry filter regression contracts."""
import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLIENT = ROOT / "src/client/dev"
STATIC = ROOT / "system/control-center/static"


class StudioDebugDockTests(unittest.TestCase):
    def test_dock_is_shared_and_windows_are_below_single_button_row(self):
        dock = (CLIENT / "StudioDebugDock.luau").read_text(encoding="utf-8")
        for token in ('TL = 0', 'MV = 1', 'MO = 2', 'CS = 3', 'local TOP = 8', 'local BUTTON_GAP = 8', 'local WINDOW_TOP = TOP + BUTTON_SIZE + BUTTON_GAP'):
            self.assertIn(token, dock)
        for file, slot in (
            ("TestLoadoutController.luau", 'DEBUG_PANEL_ID'),
            ("MovementDebugController.luau", 'DEBUG_PANEL_ID'),
            ("MonsterDebugController.luau", 'PANEL_ID'),
            ("CustomScalingDebugController.luau", '"CS"'),
        ):
            content = (CLIENT / file).read_text(encoding="utf-8")
            self.assertIn('StudioDebugDock.ButtonPosition(' + slot + ')', content)
            self.assertIn('StudioDebugDock.WindowPosition(' + slot + ',', content)
            self.assertIn('Game1DebugPanelOpen', content)

    def test_radius_is_centered_with_half_stud_server_authoritative_steps(self):
        content = (CLIENT / "TestLoadoutController.luau").read_text(encoding="utf-8")
        for token in ('radiusBox.TextXAlignment = Enum.TextXAlignment.Center',
                      'radiusMinus.Activated:Connect', 'radiusPlus.Activated:Connect',
                      'changeRadiusBy(-0.5)', 'changeRadiusBy(0.5)',
                      'radiusRemote:InvokeServer(value)', 'applyRadiusValue("default")'):
            self.assertIn(token, content)

    @unittest.skipUnless(shutil.which("node"), "Node.js required for DOM behavior test")
    def test_filter_sorts_both_lists_and_persists(self):
        script = textwrap.dedent(r'''
            const fs=require('fs');const vm=require('vm');
            const elements={};const saved={};
            function elem(id){if(!elements[id])elements[id]={_html:'',textContent:'',value:'',children:[],set innerHTML(v){this._html=v;this.children=[]},get innerHTML(){return this._html},appendChild(v){this.children.push(v);},querySelector(){return {};}};return elements[id];}
            const context={window:{},$:elem,esc:x=>String(x),toast:()=>{},request:async()=>({}),
                confirm:()=>false,localStorage:{getItem:key=>saved[key],setItem:(key,value)=>{saved[key]=value}},
                console,document:{createElement:()=>({innerHTML:'',children:[],appendChild(v){this.children.push(v)},querySelector(){return {};}})}};
            vm.createContext(context);
            vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),context);
            vm.runInContext(`weaponState.data={options:{weaponTypes:['sword','dagger','1hs']},items:[
                {slug:'z',weapon_type:'sword',name_en:'Zed',rarity:'common'},
                {slug:'a',weapon_type:'dagger',name_en:'A',rarity:'common'},
                {slug:'b',weapon_type:'sword',name_en:'Blade',rarity:'common'}
            ]};weaponRenderListFilters();weaponRenderTree();weaponRenderRows();`,context);
            const tree=elem('weapon-tree');const table=elem('weapon-rows');
            if(tree.children.map(x=>x.innerHTML).join('|').indexOf('A')>tree.children.map(x=>x.innerHTML).join('|').indexOf('Blade'))throw Error('type order wrong');
            if(tree.children.length!==3||table.children.length!==3)throw Error('render list count wrong');
            vm.runInContext(`weaponSetListType('sword')`,context);
            if(tree.children.length!==2||table.children.length!==2)throw Error('type filter wrong');
            if(!tree.children.every(x=>x.innerHTML.includes('sword')))throw Error('wrong type in rail');
            if(elem('weapon-table-type').value!=='sword'||elem('weapon-list-type').value!=='sword')throw Error('filter controls not synced');
            if(saved['game1.weapon.listType']!=='sword')throw Error('filter not persisted');
            console.log('weapons filter / sort DOM contract passed');
        ''')
        result = subprocess.run([shutil.which('node'), '-e', script, str(STATIC / 'weapon-assets.js')],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
