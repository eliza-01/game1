"""M543: authored entry safety, sprite atlas consistency, client presentation and debug language."""
import itertools
import json
import math
import re
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'system/control-center'))
from options_store import OptionsStore, normalize_debug_ui

def read(path): return (ROOT/path).read_text(encoding='utf8')

def dist_to_segment(p,a,b):
    dx,dz=b[0]-a[0],b[1]-a[1]
    t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dz)/(dx*dx+dz*dz)))
    return math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dz)

class WorldReadability(unittest.TestCase):
    def test_hunting_pockets_and_safe_roads(self):
        plan=read('src/server/dev/GameplayWorldHuntingPlan.luau')
        groups=re.findall(r'yaw=(-?\d+), points=\{(.*?)\n    \}\}',plan,re.S)
        extras=[tuple(map(int,m)) for m in re.findall(r'Vector2\.new\((-?\d+),(-?\d+)\)',plan)]
        self.assertEqual(len(extras),2)
        exits=[((-192,0),(0,-192)),((192,0),),((192,0),),((-192,0),(192,0)),((0,-192),),((0,-192),)]
        for i,(_,raw) in enumerate(groups):
            points=[tuple(map(int,p)) for p in re.findall(r'\{(-?\d+),(-?\d+)\}',raw)]
            if i==0: points+=extras
            self.assertGreaterEqual(min(math.dist(a,b) for a,b in itertools.combinations(points,2)),60)
            roads=[((0,192),(0,0))]+[((0,0),end) for end in exits[i]]
            self.assertGreaterEqual(min(dist_to_segment(p,a,b) for p in points for a,b in roads),37)
            self.assertGreaterEqual(min(math.dist((0,168),p) for p in points),60)
            self.assertTrue(all(max(map(abs,p))<184 for p in points))
            if i==0:
                melee_one=[points[0],*extras]
                self.assertLess(max(math.dist((0,168),p) for p in melee_one),min(math.dist((0,168),p) for p in points[1:8]))
        self.assertIn('if index == 1 and row.type == "ranged" then return false, 24 end',plan)
        self.assertIn('if index == 1 then return true, 20 end',plan)
        self.assertIn('record.testAggressive',read('src/server/monster/MonsterInitialAttributes.luau'))
        self.assertIn('testAggroRadius = if slot then slot.aggroRadius else nil',read('src/server/dev/GameplayTestArena.luau'))
        self.assertIn('local expectedCount = #rows + #s.layout.extraSlots',read('src/server/dev/GameplayTestService.luau'))

    def test_atlas_tiles_match_database_and_runtime_pixels(self):
        directory=ROOT/'system/control-center/static/monster-icons'
        catalog=json.loads((directory/'catalog.json').read_text())
        data=json.loads(read('config/balance/gameplay.json'))
        named={re.search(r'\(([^()]*)\)\s*$',row['name'])[1] for row in data['monsters'] if row.get('name')}
        keys={tile['name'] for tile in catalog['tiles']}
        self.assertEqual(named|{'Unknown'},keys)
        self.assertEqual(len(keys),26)
        image=Image.open(directory/'atlas.png').convert('RGBA')
        self.assertEqual(image.size,(catalog['width'],catalog['height']))
        runtime=read('src/shared/interface/MonsterIconAtlas.luau')
        for tile in catalog['tiles']:
            section=runtime.split(f'[{json.dumps(tile["name"])}] = table.freeze({{',1)[1].split('    }),',1)[0]
            generated=Image.new('RGBA',(16,16))
            for x,y,length,hexcolor in re.findall(r'\{(\d+),(\d+),(\d+),"([a-f0-9]{6})"\}',section):
                for xx in range(int(x),int(x)+int(length)):
                    generated.putpixel((xx,int(y)),tuple(bytes.fromhex(hexcolor))+(255,))
            self.assertEqual(generated.tobytes(),image.crop((tile['x'],tile['y'],tile['x']+16,tile['y']+16)).tobytes())
        icons=read('src/client/combat/MonsterIconView.luau')
        self.assertIn('delta >= 10',icons);self.assertIn('delta <= 0',icons)
        view=read('src/client/combat/HealthBarView.luau')
        self.assertIn('portraitHeight + lineHeight + statsHeight + 2',view)
        self.assertIn('portrait:Destroy()',view)
        ctl=read('src/client/combat/OverheadHealthController.luau')
        self.assertIn('playerZone == zone',ctl)
        self.assertIn('view.SetIcon(alive and sameZone, playerLevel)',ctl)
        spawner=read('src/server/monster/MonsterSpawnerService.luau')
        self.assertIn('if not record.testZone or record.testZone > 6 then',spawner)
        self.assertIn('RunService:IsStudio() and Workspace.StreamingEnabled',spawner)
        self.assertIn('model:AddPersistentPlayer(persistentOwner)',spawner)

    def test_debug_locale_migration_and_camera(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);manifest=root/'assets/manifests/options.json';manifest.parent.mkdir(parents=True)
            old=json.loads(read('assets/manifests/options.json'));old['debugUi'].pop('startedLanguage',None);old['debugUi'].pop('startLocale',None)
            manifest.write_text(json.dumps(old),encoding='utf8')
            store=OptionsStore(root)
            self.assertFalse(store.snapshot()['debugUi']['startedLanguage'])
            self.assertEqual(store.snapshot()['debugUi']['startLocale'],'auto')
            store.update({'debugUi':{'startedLanguage':True,'startLocale':'ru-ru'}})
            self.assertEqual(OptionsStore(root).snapshot()['debugUi']['startLocale'],'ru-ru')
            self.assertIn('startedLanguage = true',read_from(root/'src/shared/GameOptionsRegistry.luau'))
            for bad in (None,42,'fake',{}):
                with self.assertRaises(ValueError): normalize_debug_ui({'startLocale':bad})
        self.assertIn('CameraSync.Align(player, character, frame)',read('src/server/dev/GameplayTestArena.luau'))
        self.assertIn('configured ~= nil and Access.ClientAllowed()',read('src/client/localization/LanguageMenuController.luau'))
        self.assertIn('Decorations.Build(parent, layout)',read('src/server/dev/GameplayTestArena.luau'))
        self.assertIn('p.CanCollide=false; p.CanQuery=false; p.CanTouch=false',read('src/server/dev/GameplayWorldDecorations.luau'))

def read_from(p): return p.read_text(encoding='utf8')
