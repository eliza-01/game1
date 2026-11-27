"""Private DEV Place debug policy; actual Lua logic with mocked Roblox services."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from options_store import OptionsStore, normalize_debug_ui

class DevPlaceDebug(unittest.TestCase):
    def test_migration_and_device_settings(self):
        old = {'desktop': {'showPublishedControls': False}, 'mobile': {'showPublishedControls': True}, 'startInHub': True, 'startedLanguage': True, 'startLocale': 'ru-ru'}
        self.assertEqual(normalize_debug_ui(old)['publishedPlaceId'], '')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = OptionsStore(root)
            store.update({'debugUi': old})
            payload = store.snapshot()
            del payload['debugUi']['publishedPlaceId']
            store.manifest_path.write_text(json.dumps(payload), encoding='utf-8')
            store = OptionsStore(root)
            self.assertEqual(store.snapshot()['debugUi'], dict(old, publishedPlaceId=''))
            store.update({'debugUi': {'publishedPlaceId': '123456789012345'}})
            store.update({'debugUi': {'desktop': {'showPublishedControls': True}}})
            result = OptionsStore(root).snapshot()['debugUi']
            self.assertEqual(result, dict(old, publishedPlaceId='123456789012345', desktop={'showPublishedControls': True}))
            self.assertIn('publishedPlaceId = "123456789012345"', store.registry_path.read_text())
        for invalid in (0, 123, False, None, '0', '01', '-2', '1.2', ' 12 ', '1e5', '9007199254740992', 'https://www.roblox.com/games/12'):
            with self.assertRaises(ValueError):
                normalize_debug_ui({'publishedPlaceId': invalid})

    def test_access_matrix_and_server_authorization(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua: self.skipTest('Standalone Lua not available')
        policy = (ROOT/'src/shared/dev/PublishedDebugAccess.luau').read_text()
        authorizer = (ROOT/'src/server/dev/PublishedDebugAccessService.luau').read_text()
        # Only translate Luau type annotations and device if-expression for Lua 5.3.
        policy = policy.replace(': boolean','').replace('player: Player','player').replace('local device = if UserInputService.TouchEnabled and not UserInputService.KeyboardEnabled\n        then "mobile" else "desktop"','local device = UserInputService.TouchEnabled and not UserInputService.KeyboardEnabled and "mobile" or "desktop"')
        authorizer = authorizer.replace('player: Player','player')
        harness = '''
local studio, draft, hub, desktop, mobile, configured = false,false,false,false,false,""
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
local options={PublishedDebugPlaceId=function() return configured end,StartInGameplayHub=function() return hub end,ShowPublishedDebugControls=function(d) if d=="desktop" then return desktop else return mobile end end}
local access
require=function(n) if n=="GameOptions" then return options else return access end end
script={Parent={Parent=shared}}
game={PlaceId=42,GetService=function(_,n) return ({Players=players,RunService=rs,UserInputService=input,ReplicatedStorage=rep})[n] end}
table.freeze=function(t) return t end
task={spawn=function(f,p) f(p) end,wait=function() error("unexpected wait") end}
warn=function() end
local function scenario(s,d,h,id,pc,mo,expected,hubExpected)
 studio,draft,hub,configured,desktop,mobile=s,d,h,id,pc,mo
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
 assert(access.ClientAllowed()==(studio or (expected and pc)))
 input.TouchEnabled=true;input.KeyboardEnabled=false
 assert(access.ClientAllowed()==(studio or (expected and mo)))
end
scenario(false,false,false,"42",true,false,true,false)
scenario(false,true,true,"42",false,true,true,false)
scenario(false,true,true,"42",true,true,true,false)
scenario(false,false,false,"",true,true,false,false)
scenario(false,true,false,"43",true,true,false,false)
scenario(false,true,false,"42",false,false,false,false)
scenario(true,false,false,"",false,false,true,true)
scenario(true,true,false,"",false,false,true,false)
scenario(true,true,true,"",false,false,true,true)
'''
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            for name, text in [('policy.lua',policy), ('authorizer.lua',authorizer), ('harness.lua',harness)]:
                (p/name).write_text(text, encoding='utf-8')
            result=subprocess.run([lua,str(p/'harness.lua'),str(p/'policy.lua'),str(p/'authorizer.lua')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_options_and_debug_remotes(self):
        for name in ('index.html','options.js'):
            self.assertIn('option-published-debug-place-id',(ROOT/'system/control-center/static'/name).read_text())
        self.assertIn('not Access.ServerEnabled()', (ROOT/'src/server/weapon/WeaponSelectionService.luau').read_text())
        self.assertIn('RunService:IsStudio() and Access.GameplayTestEnabled()', (ROOT/'src/server/dev/GameplayTestService.luau').read_text())

if __name__ == '__main__': unittest.main()
