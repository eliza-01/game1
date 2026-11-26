"""Species-wide settings and guarded Studio write-through; level ATK compensation."""
from copy import deepcopy
from pathlib import Path
import json, sys, tempfile, unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'system/control-center'))
from services import game_balance as b
from api import balance as api

def read(path): return (ROOT/path).read_text(encoding='utf8')

class SpeciesAggro(unittest.TestCase):
    def setUp(self): self.data=b.load()
    def test_level_atk_and_hp_compensation(self):
        self.assertNotIn('levelDamageStep', self.data['rules'])
        self.assertEqual(self.data['levels'][0]['attackBonus'], 0)
        self.assertEqual(self.data['levels'][1]['attackBonus'], 1)
        self.assertIn('Registry.rules.baseDamage + Balance.Level(level).attackBonus',read('src/shared/balance/Balance.luau'))
        stats=read('src/server/character/CharacterStatsService.luau')
        self.assertIn('setBase(character, "Damage", Balance.BaseDamageAt(level.level))',stats)
        self.assertIn('character:SetAttribute("BaseDamage", Balance.BaseDamageAt(level.level))',stats)
    def test_species_consistency(self):
        rows=[r for r in self.data['monsters'] if r['nameEn']=='Mandragora']
        self.assertEqual(len(rows),4)
        self.assertTrue(all(r['nameRu']=='Мандрагора' and not r['aggressive'] and r['aggroRadiusStuds']==24 for r in rows))
        for key,value in [('aggroRadiusStuds',7),('aggressive',True),('nameRu','Other')]:
            draft=deepcopy(self.data); next(r for r in draft['monsters'] if r['nameEn']=='Mandragora')[key]=value
            with self.assertRaises(ValueError): b.validate(draft)
    def test_sync_persists_only_matching_species_and_rejects_stale(self):
        class Store:
            def __init__(self,items): self.items=items
            def snapshot(self): return {'items':self.items}
        deps={'weapons':Store([{'slug':slug,'weapon_type':next(r['type'] for r in self.data['weapons'] if r['id']==identity)} for slug,identity in self.data['weaponBindings'].items()]),'monsters':Store([{'slug':slug} for slug in self.data['monsterBindings']])}
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'gameplay.json';output=Path(tmp)/'BalanceRegistry.luau'
            source.write_text(json.dumps(self.data,ensure_ascii=False),encoding='utf8');output.write_text(b.render(self.data),encoding='utf8')
            # load() and save() use the same temporary project source and generated registry.
            with patch.object(b,'SOURCE',source),patch.object(b,'OUTPUT',output):
                changes=[{'nameEn':'Mandragora','oldRadius':24,'oldAggressive':False,'radius':0,'aggressive':True}]
                status,result=api.write('/api/balance/monster-aggro',lambda:{'changes':changes},deps)
                self.assertEqual((status,result),(200,{'ok':True}))
                actual=b.load();expected=deepcopy(self.data)
                for row in expected['monsters']:
                    if row['nameEn']=='Mandragora': row.update(aggroRadiusStuds=0,aggressive=True)
                self.assertEqual(actual,expected)
                self.assertEqual(api.write('/api/balance/monster-aggro',lambda:{'changes':changes},deps)[0],409)
                self.assertEqual(b.load(),expected)
    def test_debug_and_localization_contract(self):
        client=read('src/client/dev/GameplayAggroController.luau')
        for token in ('not entries[row.nameEn]', 'CanQuery=false', 'GameplayTestZone', 'SyncGameplayAggro', 'Result', 'Live preview applied; no save receipt'):
            self.assertIn(token,client)
        server=read('src/server/dev/GameplayAggroService.luau')
        self.assertIn('RunService:IsStudio()',server);self.assertIn('Access.ServerAllowed(player)',server)
        self.assertIn('Overrides.Set',server)
        bridge=read('system/studio-plugin/modules/StudioOptionsDraftBridge.luau')
        self.assertIn('/api/balance/monster-aggro',bridge);self.assertIn('folder:SetAttribute("Result"',bridge)
        view=read('src/client/combat/HealthBarView.luau')
        for token in ('MonsterNameEn','MonsterNameRu','MonsterAggressive','"Ур."','"Lv."','AggressiveMark','TextService:GetTextSize'):
            self.assertIn(token,view)
        ui=read('system/control-center/static/game-balance.js');self.assertIn('speciesEdit',ui);self.assertIn('balance-search',ui)
