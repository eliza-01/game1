"""Recipe and animation authoring contract; live contact tests in Studio companion."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'system/control-center'))
from services import game_balance as balance
from services import balance_patch_logs as logs
from timeline_store import TimelineStore, event_names_for_subject
from animation_core.common import classify_animation
from weapon_store import WEAPON_TYPES, ATTACK_MOVEMENT_DEFAULTS

class Dualswords(unittest.TestCase):
    def test_recipe_and_grade(self):
        data=balance.load()
        duals=[r for r in data['weapons'] if r['type']=='dualswords']
        self.assertEqual([r['id'] for r in duals], ['weapon_033','weapon_034'])
        self.assertEqual([r['level'] for r in duals], [30,35])
        for field,value in [('level',29),('recipe',None),('price',1)]:
            draft=deepcopy(data);draft['weapons'][-1][field]=value
            with self.assertRaises(ValueError): balance.validate(draft)
        for field,value in [('swordId','weapon_001'),('quantity',1),('fee',-1)]:
            draft=deepcopy(data);draft['weapons'][-1]['recipe'][field]=value
            with self.assertRaises(ValueError): balance.validate(draft)
        self.assertEqual(balance.OUTPUT.read_text(),balance.render(data))
        self.assertTrue(any(r['patch']==525 for r in logs.load()['entries']))
    def test_seed_design_not_mutable_stats(self):
        for sword, expected, price, result in [(125,141,3000,7500),(147,165,3500,8750)]:
            attack=int(sword*1.125+.5)
            self.assertEqual(attack,expected)
            self.assertEqual(2*price+price//2,result)
            self.assertEqual(attack//2+(attack-attack//2),attack)
            self.assertAlmostEqual(attack*180/300*1.08/(sword*180/300*1.08),1.125,delta=.005)
    def test_authoring(self):
        self.assertIn('dualswords',WEAPON_TYPES)
        self.assertEqual(ATTACK_MOVEMENT_DEFAULTS['dualswords']['animationSet'],'dualswords')
        self.assertEqual(event_names_for_subject('characters','dualswords'),{'HitFirst','HitEnd'})
        self.assertEqual(event_names_for_subject('characters','1hs'),{'HitEnd'})
        self.assertEqual(event_names_for_subject('characters','bow'),{'Release'})
        events={'HitFirst':{'normalizedTime':.25},'HitEnd':{'normalizedTime':.6}}
        self.assertEqual(TimelineStore._validate_events('characters',events,'dualswords'),events)
        for invalid in [{'HitEnd':events['HitEnd']}, {'HitFirst':events['HitEnd'],'HitEnd':events['HitFirst']}, {'HitFirst':events['HitEnd'],'HitEnd':events['HitEnd']}]:
            with self.assertRaises(ValueError): TimelineStore._validate_events('characters',invalid,'dualswords')
        clip=classify_animation(Path('human_male_dualswords_attack_01.rbxm'),'human_male')
        self.assertEqual(clip['weaponSet'],'dualswords')
    def test_runtime_contract(self):
        def read(p):return (ROOT/p).read_text()
        attack=read('src/server/combat/AttackService.luau')
        self.assertIn('MeleeHitPlan.Damage(totalDamage, contact.index, contact.count)',attack)
        self.assertIn('GameplayFallback.Allowed(character)',attack)
        policy=read('src/shared/combat/GameplayAttackFallback.luau')
        self.assertIn('RunService:IsStudio() and character:GetAttribute("GameplayTestKind") == "player"',policy)
        self.assertIn('session.weaponId ~= tostring',attack)
        equip=read('src/server/weapon/WeaponEquipService.luau')
        self.assertIn('if isDual and not dualReady and not testId then',equip)
        self.assertIn('local left = weapon:Clone()',equip)
        self.assertIn('row.requiredLevel',equip)
        self.assertIn('LEFT_EQUIPPED_NAME',equip)
        self.assertIn('RigidMount.Attach(left, leftGrip, leftBone, "weapon")',equip)
