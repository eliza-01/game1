"""M539: names, full-scale zone prototype, panels and Design projection."""
from copy import deepcopy
from pathlib import Path
import json, re, sys, unittest, xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'system/control-center'))
from services import game_balance as balance
from kanban_store import KanbanStore

def read(path): return (ROOT/path).read_text(encoding='utf-8')

class WorldDesign(unittest.TestCase):
    def test_names_and_type_contract(self):
        data=balance.load()
        self.assertEqual(len(data['monsters']),70)
        rows={(r['level'],r['type']):r for r in data['monsters']}
        for level,kind,name in [(1,'melee','Жаба (Toad)'),(2,'ranged','Мандрагора (Mandragora)'),(3,'melee','Деревянный страж (Wooden Guardian)'),(4,'melee','Живое пугало (Living Scarecrow)'),(5,'melee','Волк (Wolf)'),(8,'ranged','Скелет-лучник (Skeleton Archer)'),(9,'melee','Медведь гризли (Grizzly)'),(11,'melee','Гремлин (Gremlin)'),(30,'melee','Древний дракон (Wyrm)')]:
            self.assertEqual(f"{rows[level,kind]['nameRu']} ({rows[level,kind]['nameEn']})",name)
        self.assertEqual(sum(bool(row['nameEn']) for row in rows.values()),55)
        self.assertEqual(len({row['nameEn'] for row in rows.values() if row['nameEn']}),25)
        for name in ([],1,'a'*101,'a\nb'):
            changed=deepcopy(data);changed['monsters'][0]['nameEn']=name
            with self.assertRaises(ValueError): balance.validate(changed)
        self.assertEqual(data['monsterBindings']['gremlin'],'monster_001') # existing production spawn unchanged
        self.assertIn("else if(key==='nameEn'||key==='nameRu')",read('system/control-center/static/game-balance.js'))
    def test_design_runtime_topology_and_images(self):
        card=KanbanStore(ROOT).detail('KBN-0031');spec=card['spec']
        self.assertTrue(card['card']['favorite'])
        rows=re.findall(r'^\| (.+?) \| (\d+)–(\d+) \| ([12]) \| ([1-4]) \|',spec,re.M)
        self.assertEqual(len(rows),6)
        lua=read('src/server/dev/GameplayTestLayout.luau')
        for name,lo,hi,col,row in rows:
            self.assertIn(f'name="{name}", low={lo}, high={hi}, col={col}, row={row}',lua)
            self.assertIn(f'## {name} · LVL {lo}–{hi}',spec)
        imgs=re.findall(r'!\[[^\]]+\]\((design-zones/[^)]+\.svg)\)',spec)
        self.assertEqual(len(set(imgs)),6)
        for img in imgs:
            tree=ET.parse(ROOT/'system/control-center/static'/img)
            self.assertEqual(tree.getroot().tag,'{http://www.w3.org/2000/svg}svg')
            self.assertNotIn('http://',read('system/control-center/static/'+img).replace('http://www.w3.org/2000/svg',''))
        self.assertIn('img.loading=\'lazy\'',read('system/control-center/static/kanban.js'))
        self.assertIn('local ZONE_SIZE = 384',lua)
        self.assertIn('local GAP = 24',lua)
    def test_gear_catalogue_and_authority(self):
        d=balance.load();layout=read('src/server/dev/GameplayTestLayout.luau'); tiers=re.findall(r'gear=\{(\d+),(\d+),(\d+)\}',layout)
        self.assertEqual(len(tiers),8)
        for row in tiers:
            levels=list(map(int,row));self.assertEqual(levels,sorted(set(levels)))
            for level in levels:
                self.assertTrue(any(x['level']==level and x['type']=='sword' for x in d['weapons']))
                self.assertTrue(any(x['level']==level for x in d['armor']))
        svc=read('src/server/dev/GameplayTestService.luau');panels=read('src/server/dev/GameplayTestPanels.luau');loadout=read('src/server/dev/GameplayTestLoadout.luau')
        for guard in ('actor~=s.player','not allowed(actor)','not active(s)','s.guide','busy[actor]','(root.Position-part.Position).Magnitude>12','GameplayTestOwner','Loadout.Stock(actor,level)','apply(s,selection)','GameplayTestStock'):
            self.assertIn(guard,svc)
        self.assertIn('prompt.Triggered:Connect',panels)
        self.assertIn('Loadout.Validate({level=level,weapon=weapon.id,armor=armor.id,upgrade=0})',loadout)
        self.assertIn('weapon=weapon or fallback',loadout)
        self.assertIn('GameplayTestEquipment',loadout)
        self.assertIn('GameplayTestEquipment',read('src/client/combat/PlayerHealthHudController.luau'))
        self.assertIn('GameplayTestStock',read('src/client/dev/GameplayTestController.luau'))
        self.assertIn('Arena.Warp(character,origin)',svc)
