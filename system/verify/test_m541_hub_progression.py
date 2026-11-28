"""M541: scoped hub option, transient XP and release hunting pockets."""
import json
import tempfile
import unittest
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'system/control-center'))
from options_store import OptionsStore, normalize_debug_ui

def read(path): return (ROOT/path).read_text(encoding='utf8')

class HubProgression(unittest.TestCase):
    def test_option_migration_and_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); manifest=root/'assets/manifests/options.json'
            manifest.parent.mkdir(parents=True)
            old=json.loads(read('assets/manifests/options.json'))
            old['debugUi'].pop('startInHub',None)
            manifest.write_text(json.dumps(old),encoding='utf8')
            store=OptionsStore(root)
            self.assertFalse(store.snapshot()['debugUi']['startInHub'])
            for value in (True,False,True):
                result=store.update({'debugUi':{'startInHub':value}})
                self.assertEqual(result['debugUi']['startInHub'],value)
                self.assertEqual(result['debugUi']['showPublishedControls'],old['debugUi']['showPublishedControls'])
                self.assertIn('startInHub = '+str(value).lower(),(root/'src/shared/GameOptionsRegistry.luau').read_text())
            result=store.update({'debugUi':{'showPublishedControls':False}})
            self.assertTrue(result['debugUi']['startInHub'])
            self.assertTrue(OptionsStore(root).snapshot()['debugUi']['startInHub'])
        for invalid in ('true',1,None,{},[]):
            with self.assertRaises(ValueError): normalize_debug_ui({'startInHub':invalid})

    def test_server_scope_and_shared_progression(self):
        server=read('src/server/character/CharacterProgressionService.luau')
        loadout=read('src/server/dev/GameplayTestLoadout.luau')
        view=read('src/server/character/CharacterProgressionView.luau')
        self.assertIn('DamageSignals.Event:Connect',server)
        self.assertLess(server.index('Loadout.Reward(player, attacker, target)'),server.index('record.xp = xp; record.gold = gold'))
        self.assertIn('if Loadout.Get(player) then return end',server)
        for token in ('RunService:IsStudio()', 'player.Character ~= character', 'target:GetAttribute("Game1GameplayTestOwner") ~= player.UserId', 'target:GetAttribute("GameplayTestKind") ~= "zone"', 'GameplayGuideTrial', 'if not row or row.skills then return end'):
            self.assertIn(token,loadout)
        self.assertIn('if selection and selection.xp == nil then',loadout)
        self.assertIn('selection.xp = Balance.Threshold(selection.level)',loadout)
        self.assertIn('selection.level = Balance.LevelForXP(selection.xp)',loadout)
        self.assertIn('ProgressionView.Publish(character, selection.xp, selection.gold)',loadout)
        self.assertNotIn('CharacterCreationProfileStore',loadout.split('local Loadout')[1])
        self.assertIn('Stats.SetProgressionLevel(character, level)',view)
        self.assertIn('xp - Balance.Threshold(level)',view)

    def test_hub_policy_and_autostart(self):
        server=read('src/server/dev/GameplayTestService.luau')
        for token in ('RunService:IsStudio() and Access.GameplayTestEnabled() and Access.ServerAllowed(player)', 'not s.guide and #s.group == 0 and not s.groupStarting', 'PointToObjectSpace(root.Position)', 'math.abs(point.Z) <= half', 'math.abs(point.Y) < 12', 'if inHub then 3 else nil', 'Options.StartInGameplayHub()', 'autoAttempted[player] = true', 'Loadout.Stock(player, 1)', 'CombatHitboxCount', 'CharacterCreationStatus', 'busy[player]'):
            self.assertIn(token,server)
        self.assertIn('not attackActive and nextMode == "Run"',read('src/client/character/MovementController.luau'))
        self.assertIn('not attackLowerBodyActive and character:GetAttribute("GameplayTestHubRunMultiplier") == 3',read('src/client/character/animation/CharacterAnimationController.luau'))
        self.assertIn('id="option-start-in-hub"',read('system/control-center/static/index.html'))
        self.assertIn("startInHub:$('option-start-in-hub').checked",read('system/control-center/static/options.js'))

    def test_current_database_has_level_one_progression(self):
        data=json.loads(read('config/balance/gameplay.json'))
        xp=data['levels'][0]['xpNext']
        reward=next(r['xp'] for r in data['monsters'] if r['level']==1 and r['type']=='melee')
        self.assertGreater(xp,0); self.assertGreater(reward,0)
        self.assertGreaterEqual(((xp+reward-1)//reward)*reward,xp)
