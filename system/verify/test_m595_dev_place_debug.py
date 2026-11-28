"""Global published debug policy (M655 replaces M595); actual Lua logic with mocked Roblox services."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from options_store import OptionsStore, normalize_debug_ui, migrate_debug_ui

class DevPlaceDebug(unittest.TestCase):
    def test_one_time_migration_and_global_setting(self):
        for pc in (False, True):
            for mobile in (False, True):
                old = {'desktop': {'showPublishedControls': pc}, 'mobile': {'showPublishedControls': mobile},
                       'startInHub': True, 'startedLanguage': True, 'startLocale': 'ru-ru', 'publishedPlaceId': '42'}
                expected = dict(showPublishedControls=pc or mobile, startInHub=True, startedLanguage=True, startLocale='ru-ru')
                self.assertEqual(migrate_debug_ui(old), expected)
                self.assertEqual(migrate_debug_ui(expected), expected)
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    store = OptionsStore(root)
                    payload = store.snapshot()
                    payload['debugUi'] = old
                    store.manifest_path.write_text(json.dumps(payload), encoding='utf-8')
                    store = OptionsStore(root)
                    self.assertEqual(store.snapshot()['debugUi'], expected)
                    for enabled in (False, True, False):
                        result = store.update({'debugUi': {'showPublishedControls': enabled}})
                        self.assertEqual(result['debugUi'], dict(expected, showPublishedControls=enabled))
                        self.assertEqual(OptionsStore(root).snapshot(), result)
                        generated = store.registry_path.read_text(encoding='utf-8')
                        self.assertIn('showPublishedControls = '+str(enabled).lower(), generated)
                        self.assertNotIn('publishedPlaceId', generated)
                    self.assertEqual(result['healthUi'], payload['healthUi'])
                    self.assertEqual(result['combat'], payload['combat'])
        for invalid in (0, 1, 'true', None, {}, []):
            with self.assertRaises(ValueError):
                normalize_debug_ui({'showPublishedControls': invalid})
        for legacy in ({'publishedPlaceId': '42'}, {'mobile': {'showPublishedControls': True}}):
            with self.assertRaises(ValueError): normalize_debug_ui(legacy)

    def test_access_matrix_and_server_authorization(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua: self.skipTest('Standalone Lua not available')
        policy = (ROOT/'src/shared/dev/PublishedDebugAccess.luau').read_text(encoding='utf-8')
        authorizer = (ROOT/'src/server/dev/PublishedDebugAccessService.luau').read_text(encoding='utf-8')
        # Only translate Luau type annotations for Lua 5.3.
        policy = policy.replace(': boolean','').replace('player: Player','player')
        authorizer = authorizer.replace('player: Player','player')
        harness = '''
local studio, draft, hub, enabled = false,false,false,false
local function makePlayer(id)
 local p={UserId=id, attrs={}}
 function p:GetAttribute(k) return self.attrs[k] end
 function p:SetAttribute(k,v) self.attrs[k]=v end
 return p
end
local owner,tester=makePlayer(1),makePlayer(2)
local key="Game1PublishedDebugAuthorized"
local listener, connections
local players={LocalPlayer=tester,PlayerAdded={Connect=function(_,f) listener=f;connections=connections+1 end},GetPlayers=function() return {owner,tester} end}
local input={TouchEnabled=false,KeyboardEnabled=true}
local rs={IsStudio=function() return studio end}
local shared={WaitForChild=function(_,n) return n end}
local rep={WaitForChild=function() return {WaitForChild=function() return shared end} end,FindFirstChild=function() if draft then return {} end end}
local options={StartInGameplayHub=function() return hub end,ShowPublishedDebugControls=function(...) assert(select("#",...)==0);return enabled end}
local access
require=function(n) if n=="GameOptions" then return options else return access end end
script={Parent={Parent=shared}}
game={PlaceId=42,GetService=function(_,n) return ({Players=players,RunService=rs,UserInputService=input,ReplicatedStorage=rep})[n] end}
table.freeze=function(t) return t end
task={spawn=function(f,p) f(p) end,wait=function() error("unexpected wait") end}
warn=function() end
local function scenario(s,d,h,id,on,expected,hubExpected)
 studio,draft,hub,enabled=s,d,h,on;game.PlaceId=id
 connections=0;listener=nil; owner.attrs={};tester.attrs={}
 access=assert(loadfile(arg[1]))()
 assert(access.ServerEnabled()==expected)
 assert(access.GameplayTestEnabled()==hubExpected)
 if not studio then assert(not access.ServerAllowed(tester)) end
 local svc=assert(loadfile(arg[2]))();svc.Start();svc.Start()
 assert(connections==(expected and 1 or 0))
 if expected then
  assert(access.ServerAllowed(owner) and access.ServerAllowed(tester))
  local newcomer=makePlayer(999);listener(newcomer);assert(access.ServerAllowed(newcomer))
 else
  tester:SetAttribute(key,true);assert(not access.ServerAllowed(tester))
 end
 input.TouchEnabled=false;input.KeyboardEnabled=true
 assert(access.ClientAllowed()==expected)
 input.TouchEnabled=true;input.KeyboardEnabled=false
 assert(access.ClientAllowed()==expected)
end
for _,id in ipairs({0,42,43,123456789012345}) do
 for _,d in ipairs({false,true}) do
  scenario(false,d,false,id,true,true,false)
  scenario(false,d,true,id,false,false,false)
 end
end
scenario(true,false,false,0,false,true,true)
scenario(true,true,false,0,false,true,false)
scenario(true,true,true,0,false,true,true)
'''
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            for name, text in [('policy.lua',policy), ('authorizer.lua',authorizer), ('harness.lua',harness)]:
                (p/name).write_text(text, encoding='utf-8')
            result=subprocess.run([lua,str(p/'harness.lua'),str(p/'policy.lua'),str(p/'authorizer.lua')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_options_and_debug_remotes(self):
        for name in ('index.html','options.js'):
            self.assertNotIn('option-published-debug-place-id',(ROOT/'system/control-center/static'/name).read_text(encoding='utf-8'))
            self.assertIn('option-published-debug-buttons',(ROOT/'system/control-center/static'/name).read_text(encoding='utf-8'))
        self.assertIn('not Access.ServerEnabled()', (ROOT/'src/server/weapon/WeaponSelectionService.luau').read_text(encoding='utf-8'))
        self.assertIn('RunService:IsStudio() and Access.GameplayTestEnabled()', (ROOT/'src/server/dev/GameplayTestService.luau').read_text(encoding='utf-8'))

if __name__ == '__main__': unittest.main()
