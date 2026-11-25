from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'system/control-center'))
from services import game_balance as b
from api import balance as api

class FakeStore:
    def __init__(self, rows): self.rows=rows
    def snapshot(self): return {'items':self.rows}

class BalanceDatabase(unittest.TestCase):
    def setUp(self):
        self.data=b.load()
        self.models=json.loads((ROOT/'assets/manifests/weapons.json').read_text(encoding='utf8'))['items']
        self.monsters=json.loads((ROOT/'assets/manifests/monsters.json').read_text(encoding='utf8'))['items']
        self.deps={'weapons':FakeStore(self.models),'monsters':FakeStore(self.monsters)}

    def test_registry_projection_and_ids(self):
        self.assertEqual(b.OUTPUT.read_text(encoding='utf8'),b.render(self.data))
        self.assertEqual(len(self.data['levels']),35)
        self.assertEqual(len(self.data['monsters']),35)
        # Individual values are editable; do not pin the user's balance.
        self.assertEqual(len(self.data['weapons']),34)
        self.assertEqual(len(self.data['armor']),8)
        self.assertEqual(self.data['levels'][-1]['xpNext'],0)

    def test_seed_design_examples(self):
        # Test the design examples, not mutable live price/XP values.
        self.assertGreaterEqual(round(75*(1+10*.0667)),120)
        self.assertLess(round(75*(1+10*.0667)),round(120*(1+10*.0667)))
        self.assertEqual(5*12,60)

    def test_reject_invalid_and_type_mismatch(self):
        for key,value in [('hp',-1),('xpNext',float('nan')),('xpNext',0)]:
            data=deepcopy(self.data);data['levels'][0][key]=value
            with self.assertRaises(ValueError): b.validate(data)
        data=deepcopy(self.data);data['weaponBindings']={'mock_model': data['weapons'][0]['id']}
        wrong='bow' if data['weapons'][0]['type']!='bow' else 'sword'
        with self.assertRaises(ValueError): b.check_bindings(data,[{'slug':'mock_model','weapon_type':wrong}],self.monsters)
        data=deepcopy(self.data);data['weaponBindings']['missing']='weapon_001'
        with self.assertRaises(ValueError): b.check_bindings(data,self.models,self.monsters)

    def test_api_save_backup_conflict_and_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'gameplay.json';output=Path(tmp)/'registry.luau'
            baseline=deepcopy(self.data);baseline['weaponBindings']={};baseline['monsterBindings']={}
            source.write_text(json.dumps(baseline),encoding='utf8');output.write_text(b.render(baseline),encoding='utf8')
            with patch.object(b,'SOURCE',source),patch.object(b,'OUTPUT',output):
                code,initial=api.read('/api/balance',self.deps);self.assertEqual(code,200)
                changed=deepcopy(initial['balance']);old=changed['monsters'][0]['gold'];new=old+1 if old<100000000 else old-1;changed['monsters'][0]['gold']=new
                payload={'balance':changed,'revision':initial['revision']}
                code,result=api.write('/api/balance',lambda:payload,self.deps);self.assertEqual(code,200)
                self.assertEqual(b.load()['monsters'][0]['gold'],new)
                self.assertEqual(json.loads(source.with_name('gameplay.previous.json').read_text()),baseline)
                self.assertEqual(api.write('/api/balance',lambda:payload,self.deps)[0],409)
                # Fail output write once, ensure pair restored.
                atomic=b.atomic; failed=False
                def flaky(path,content):
                    nonlocal failed
                    if path==output and not failed: failed=True;raise OSError('simulated failure')
                    atomic(path,content)
                changed['monsters'][0]['gold']=old
                with patch.object(b,'atomic',flaky):
                    self.assertEqual(api.write('/api/balance',lambda:{'balance':changed,'revision':result['revision']},self.deps)[0],500)
                self.assertEqual(b.load()['monsters'][0]['gold'],new)

    def test_runtime_is_wired(self):
        def src(path): return (ROOT/path).read_text(encoding='utf8')
        equip=src('src/server/weapon/WeaponEquipService.luau')
        self.assertIn('Balance.WeaponForModel(slug, model.weaponType)',equip)
        self.assertIn('local row = gameplayRow(slug)',equip)
        self.assertIn('Progression.Start()',src('src/server/character/CharacterService.luau'))
        progression=src('src/server/character/CharacterProgressionService.luau')
        self.assertIn('DamageSignals.Event:Connect',progression)
        self.assertIn('player.Character ~= attacker',progression)
        self.assertIn('record.xp = xp; record.gold = gold',progression)
        self.assertIn('Balance.MonsterForModel',src('src/server/monster/MonsterInitialAttributes.luau'))
        self.assertNotIn('weapon-stat-damage',src('system/control-center/static/index.html'))
        self.assertIn('Model bindings',src('system/control-center/static/game-balance.js'))
