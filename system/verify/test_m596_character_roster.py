"""M596 static integration contracts + executable pure roster cases when Luau CLI exists."""
from pathlib import Path
import json
import re
import tempfile
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]

def read(relative):
    return (ROOT / relative).read_text(encoding='utf8')

SERVER = 'src/server/character/'
CLIENT = 'src/client/character/'

class CharacterRosterM596(unittest.TestCase):
    def test_pure_roster_behavior(self):
        cli = shutil.which('luau')
        if cli:
            subprocess.run([cli, 'system/verify/character_roster_m596.luau'], cwd=ROOT, check=True, timeout=20)
            return
        # The roster module is engine-free Lua with only Luau annotations and
        # table.freeze. Exercise the same implementation under texlua when
        # the standalone Luau CLI is not installed (not a Luau syntax check).
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua:
            self.skipTest('Luau / Lua interpreter unavailable')
        module = read(SERVER+'CharacterProfileRoster.luau')
        module = re.sub(r'^(local function|function) ([^(]+)\(([^)]*)\)(?::[^\n]*)?$',
                        lambda m: m[1]+' '+m[2]+'('+re.sub(r':\s*[A-Za-z]+\??', '', m[3])+')',
                        module, flags=re.M)
        script = read('system/verify/character_roster_m596.luau').replace(
            'require("../../src/server/character/CharacterProfileRoster")', 'assert(loadfile(arg[1]))()')
        script = 'table.freeze = table.freeze or function(t) return t end\n' + script
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder/'roster.lua').write_text(module, encoding='utf8')
            (folder/'test.lua').write_text(script, encoding='utf8')
            subprocess.run([lua, str(folder/'test.lua'), str(folder/'roster.lua')], check=True, timeout=20)

    def test_legacy_migration_and_independent_identity(self):
        roster = read(SERVER+'CharacterProfileRoster.luau')
        store = read(SERVER+'CharacterCreationProfileStore.luau')
        self.assertIn('Roster.Limit = 5', roster)
        self.assertIn('raw.schemaVersion == 1 and valid(raw)', roster)
        self.assertIn('local character = Roster.Copy(raw)', roster)
        self.assertIn('character.id = "legacy"', roster)
        self.assertIn('id = id, archetype = archetype, appearance = Roster.Copy(appearance), xp = 0, gold = 0', roster)
        self.assertIn('database:GetAsync(key(player))', store)
        self.assertIn('GetDataStore("game1_character_profiles_v1")', store)
        self.assertIn('Roster.Find(session.document, session.document.selectedId)', store)
        self.assertIn('Balance.NormalizeXP(record.xp)', store)
        self.assertIn('Balance.NormalizeGold(record.gold)', store)
        self.assertIn('record.lastWorldCFrame = frame', store)
        self.assertIn('decodeFrame(record.lastWorldCFrame)', store)
        self.assertIn('local record = Profiles.Get(player)', read(SERVER+'CharacterProgressionService.luau'))

    def test_compare_and_swap_no_stale_overwrite_or_session_fallback(self):
        store = read(SERVER+'CharacterCreationProfileStore.luau')
        roster = read(SERVER+'CharacterProfileRoster.luau')
        self.assertIn('return "player_" .. tostring(player.UserId)', store)
        self.assertIn('if not Roster.Matches(previous, session.expected) then return nil end', store)
        self.assertIn('previous.revision == expected.revision', roster)
        self.assertIn('return Roster.Equal(previous, expected)', roster)
        self.assertLess(store.index('candidate.revision = HttpService:GenerateGUID(false)'), store.index('for _ = 1, 2 do'))
        self.assertIn('previous.revision == candidate.revision', store)
        self.assertIn('session.blocked = true', store)
        self.assertIn('if not RunService:IsStudio() then return false end', store)
        self.assertIn('if not document or (not ok and not RunService:IsStudio()) then', store)
        self.assertNotIn('RemoveAsync', store)
        self.assertIn('table.remove(candidate.characters, index)', roster)
        self.assertIn('session.document.selectedId ~= id', store)

    def test_gateway_stage_and_owned_id_guards(self):
        gateway = read(SERVER+'CharacterCreationGateway.luau')
        roster = read(SERVER+'CharacterRosterGateway.luau')
        self.assertIn('if self.enabled then SavedColors.Bind(remotes); Roster.Bind(self, remotes) end', gateway)
        self.assertIn('return gateway:Request(player, function() return RosterGateway.Change', roster)
        self.assertIn('if stage ~= "selection" then', roster)
        self.assertIn('id ~= selectedId', roster)
        self.assertIn('if #list >= gateway.profiles.Limit then', roster)
        self.assertIn('if not gateway.profiles.Get(player) then gateway:Stage(player, "creation") end', roster)
        self.assertIn('if action == "cancel" and stage == "creation" and #list > 0 then', roster)
        self.assertIn('record.id ~= selectedId', gateway)
        self.assertIn('if stage == "selection" and existing then', gateway)
        self.assertIn('if not self.profiles.Ready(player)', gateway)
        self.assertIn('if not gateway.profiles.Ready(player)', roster)
        self.assertNotIn('game:GetService("RunService"):IsStudio()', roster)
        self.assertIn('CharacterCreationStatus") == "world"', read(SERVER+'CharacterService.luau'))

    def test_client_confirmation_and_preview_independence(self):
        controller = read(CLIENT+'CharacterCreationController.luau')
        view = read(CLIENT+'CharacterRosterView.luau')
        self.assertIn('if confirmingDelete then rosterAction("delete", selectedId)', controller)
        self.assertIn('else confirmingDelete = true; refresh() end', controller)
        self.assertIn('if confirmingDelete then confirmingDelete = false; status.Text = ""; refresh(); return end', controller)
        self.assertIn('enter.Active = not busy and not confirmingDelete', controller)
        self.assertIn('selectedId = response.selectedId', controller)
        self.assertIn('if changedSlot then currentPreview:KeepOnly(nil)', controller)
        self.assertIn('revisions.human_male += 1; revisions.human_female += 1', controller)
        self.assertIn('readFailed = true -- management stays available even for invalid appearance', controller)
        self.assertIn('enable(controls.deleteCharacter, selection and not busy and known)', view)
        self.assertIn('#characters < limit', view)
        self.assertIn('elseif stage == "selection" and pending and not retry and not selectedReady then', controller)
        self.assertIn('Request.Invoke(remote, function() return epoch == token and not leaving end, 35, selectedId)', controller)

    def test_catalog_rojo_and_mechanics_contracts(self):
        catalog = json.loads(read('assets/manifests/game-localization.json'))
        for key in ('delete_character','confirm_delete','delete_warning','profile_reload'):
            self.assertEqual(set(catalog['groups']['creation']['creation.'+key]['translations']), set(catalog['locales']))
        project = json.loads(read('default.project.json'))['tree']
        self.assertEqual(project['ServerScriptService']['Game1Server']['$path'], 'src/server')
        self.assertEqual(project['StarterPlayer']['StarterPlayerScripts']['Game1Client']['$path'], 'src/client')
        mechanics = read('system/control-center/mechanics/catalog.py')
        for path in (SERVER+'CharacterProfileRoster.luau', SERVER+'CharacterRosterGateway.luau', CLIENT+'CharacterRosterView.luau'):
            self.assertIn(path, mechanics)

if __name__ == '__main__': unittest.main()
