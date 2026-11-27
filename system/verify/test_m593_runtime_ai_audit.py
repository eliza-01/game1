"""Published navigation opt-in, debug startup boundary, and Options round trip."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from options_store import OptionsStore, normalize_monster_ai
from services.runtime_script_freshness import expected_scripts
from kanban_store import KanbanStore


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


class RuntimeAiAudit(unittest.TestCase):
    def test_runtime_option_migrates_and_preserves_values(self):
        old = {'noDamageReturnSeconds': 44, 'experimentalNavigation': {'enabled': False, 'searchDistance': 80}}
        result = normalize_monster_ai({}, old)
        self.assertFalse(result['experimentalNavigation']['runtimeEnabled'])
        with tempfile.TemporaryDirectory() as tmp:
            store = OptionsStore(Path(tmp))
            store.update({'monsterAi': old})
            store.update({'monsterAi': {'experimentalNavigation': {'runtimeEnabled': True}}})
            nav = OptionsStore(Path(tmp)).snapshot()['monsterAi']['experimentalNavigation']
            self.assertEqual((nav['enabled'], nav['runtimeEnabled'], nav['searchDistance']), (False, True, 80))
            self.assertIn('runtimeEnabled = true,', store.registry_path.read_text())
        for invalid in (1, 'true', None):
            with self.assertRaises(ValueError):
                normalize_monster_ai({'experimentalNavigation': {'runtimeEnabled': invalid}})
        self.assertIn('source.runtimeEnabled == true', read('src/shared/GameOptions.luau'))
        self.assertIn('option-nav-runtime-enabled', read('system/control-center/static/options.js'))
        self.assertIn('id="option-nav-runtime-enabled"', read('system/control-center/static/index.html'))

    def test_backend_and_prepare_matrix(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua:
            self.skipTest('Standalone Lua interpreter unavailable')
        # Exercise actual backend selection and Prepare with engine stubs;
        # only translate the unrelated Luau expression in NavigateTo to Lua.
        source = read('src/server/monster/MonsterNavigationDispatch.luau').replace(
            'if enabled then "Experimental" else "Legacy"', 'enabled and "Experimental" or "Legacy"')
        harness = '''
local studio,override,prepared,draft=false,nil,0,false
local config={enabled=true,runtimeEnabled=false}
local model={GetAttribute=function(_,name) return nil end}
local agent={model=model}
local modules={MonsterNavigationConfig=config,MonsterNavigationTrace={},MonsterChaseNavigation={},
 MonsterExperimentalNavigation={Initialize=function() prepared=prepared+1 end},MonsterNavigationSpeed={},MonsterBlockedPursuit={}}
table.freeze=function(t) return t end
script={Parent={WaitForChild=function(_,name) return name end}}
require=function(name) return assert(modules[name],name) end
game={GetService=function(_,name)
 if name=="RunService" then return {IsStudio=function() return studio end} end
 if name=="ReplicatedStorage" then return {FindFirstChild=function() if draft then return {} end end} end
 return {GetAttribute=function() return override end}
end}
local function check(s,e,r,o,want,d)
 studio,config.enabled,config.runtimeEnabled,override,draft=s,e,r,o,d==true
 prepared=0
 local d=assert(loadfile(arg[1]))()
 assert(d.Enabled(agent)==want)
 d.Prepare(); assert(prepared==(want and 1 or 0))
end
check(false,true,false,true,false)
check(false,true,true,false,true)
check(false,false,true,true,false)
check(false,true,true,nil,true)
check(true,true,false,nil,true)
check(true,true,true,false,false)
check(true,false,false,true,true)
check(true,false,true,nil,false)
check(true,true,false,nil,false,true)
check(true,true,true,nil,true,true)
check(true,true,false,true,true,true)
'''
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / 'dispatch.lua').write_text(source)
            (p / 'test.lua').write_text(harness)
            result = subprocess.run([lua, str(p / 'test.lua'), str(p / 'dispatch.lua')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_debug_catalog_skips_require_when_disabled(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua:
            self.skipTest('Standalone Lua interpreter unavailable')
        source = read('src/server/bootstrap/ServiceCatalog.luau').replace('root: Instance', 'root').replace('(): boolean', '()')
        harness = '''
local studio,enabled,draft,hub=false,false,false,false
local requires={}
local node={}
node.WaitForChild=function(_,name) if name=="Game1Shared" or name=="dev" or name=="character" or name=="combat" or name=="monster" or name=="npc" or name=="world" or name=="weapon" or name=="localization" then return node end return name end
game={GetService=function(_,name) if name=="RunService" then return {IsStudio=function() return studio end} end return node end}
require=function(name)
 if name=="PublishedDebugAccess" then return {ServerEnabled=function() return enabled end,GameplayTestEnabled=function() return studio and (not draft or hub) end} end
 requires[name]=true; return {Start=function() end}
end
local catalog=assert(loadfile(arg[1]))()
local debugNames={PublishedDebugAccessService=true,CustomScalingDebugService=true,TestLoadoutService=true,HouseSocketDebugService=true,CameraDebugService=true,HealthUiDebugService=true,UiPresentationDebugService=true}
local studioNames={GameplayTestService=true,GameplayAggroService=true}
local function check(s,e,d,h)
 studio,enabled,draft,hub,requires=s,e,d,h,{}
 for _,entry in ipairs(catalog.Build(node)) do entry.start() end
 for name in pairs(debugNames) do assert((requires[name]==true)==e,name) end
 for name in pairs(studioNames) do assert((requires[name]==true)==(s and (not d or h)),name) end
 assert(requires.MonsterAIService and requires.CharacterService and requires.WeaponSelectionService)
end
check(false,false,false,false); check(false,true,false,true); check(true,true,false,false); check(true,true,true,false); check(true,true,true,true)
'''
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / 'catalog.lua').write_text(source)
            (p / 'test.lua').write_text(harness)
            result = subprocess.run([lua, str(p / 'test.lua'), str(p / 'catalog.lua')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        client = read('src/client/init.client.luau')
        gate = client.index('if DebugAccess.ClientAllowed() then')
        for name in ('GameplayTestController', 'GameplayAggroController', 'GameplayBufferController', 'TestLoadoutController', 'HouseSocketDebugController'):
            self.assertGreater(client.index(name), gate)
        self.assertIn('if started or not Access.ServerEnabled() then return end', read('src/server/dev/PublishedDebugAccessService.luau'))
        self.assertIn('if compiledRuntime() then return false end', read('src/shared/dev/PublishedDebugAccess.luau'))
        self.assertIn('RunService:IsStudio() and (not compiledRuntime() or Options.StartInGameplayHub())', read('src/shared/dev/PublishedDebugAccess.luau'))
        self.assertIn('if DebugAccess.GameplayTestEnabled() then', client)

    def test_rojo_contract_and_kanban(self):
        scripts, _ = expected_scripts(ROOT)
        for name in ('MonsterNavigationDispatch', 'MonsterRescueGraph', 'MonsterRescueSampling', 'MonsterBlockedPursuit', 'MonsterHomeRecall'):
            self.assertIn(('ServerScriptService', 'Game1Server', 'monster', name), scripts)
        card = KanbanStore(ROOT).detail('KBN-0032')['card']
        self.assertEqual(card['status'], 'IN_PROGRESS')
        self.assertTrue(any(a['status'] == 'NOT_RUN' and 'Runtime Draft' in a['title'] for a in card['acceptance']))

    def test_disabled_wait_does_not_allocate_geometry_callback(self):
        source = read('src/server/monster/MonsterExperimentalNavigation.luau')
        blocked = source.split('local function stepBlocked(', 1)[1].split('function Navigation.NavigateTo', 1)[0]
        self.assertIn('if before~="Wait" then', blocked)
        self.assertIn('GetAttribute("MonsterRecoveryStuckSeconds")~=seconds', blocked)
        self.assertIn('local diagnosticAttributes=game:GetService("RunService"):IsStudio()', source)


if __name__ == '__main__':
    unittest.main()
