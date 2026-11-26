from copy import deepcopy
from pathlib import Path
import json, math, sys, unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'system/control-center'))
from services import game_balance as b, skill_balance as s

def read(path): return (ROOT/path).read_text(encoding='utf8')

class SkillCatalogue(unittest.TestCase):
    def setUp(self): self.data=b.load()
    def test_catalogue_projection(self):
        self.assertEqual(self.data['schemaVersion'],4)
        self.assertEqual(len(self.data['monsters']),70)
        self.assertEqual({x['effect'] for x in self.data['skills']},s.DEBUFFS|(s.BUFFS-{'haste'}))
        resolved=s.resolve(self.data)
        self.assertEqual(len(resolved),len(self.data['skilledMonsters']))
        self.assertEqual(b.render(self.data),b.OUTPUT.read_text(encoding='utf8'))
        for r in resolved:
            base=next(x for x in self.data['monsters'] if x['id']==r['baseId'])
            self.assertEqual((r['hp'],r['attackSpeed'],r['xp'],r['gold']),(base['hp'],base['attackSpeed'],base['xp'],base['gold']))
    def test_budget_seed_math_and_toggle(self):
        data=deepcopy(self.data)
        profile=data['skilledMonsters'][0];profile['level']=20;profile['type']='melee'
        profile['skills']=[{'skillId':'skill_poison','downgrade':True,'trigger':'cast','hpBelow':50}]
        base=next(x for x in data['monsters'] if x['level']==20 and x['type']=='melee')
        poison=next(x for x in data['skills'] if x['id']=='skill_poison')
        poison.update(duration=4,cooldown=12,power=15,tick=1)
        base.update(damage=84,attackSpeed=100,critChance=5)
        data['rules']['critMultiplier']=2
        row=s.resolve(data)[0]
        self.assertAlmostEqual(row['factor'],1/(1+max(0,.6*1.83/12/1.05-data['rules']['monsterCastSeconds']/12)))
        self.assertEqual(row['damage'],math.floor(base['damage']*row['factor']+.5))
        profile['skills'][0]['downgrade']=False
        self.assertEqual(s.resolve(data)[0]['damage'],84)
        profile['skills'][0]['downgrade']=True
        profile['skills'].append({'skillId':'skill_stun','downgrade':True,'trigger':'cast','hpBelow':50})
        stun=next(x for x in data['skills'] if x['id']=='skill_stun');stun.update(duration=1.5,cooldown=18,power=100)
        combo=s.resolve(b.validate(data))[0]
        self.assertAlmostEqual(combo['factor'],row['factor']/(1+max(0,.125-data['rules']['monsterCastSeconds']/18)))
        self.assertEqual(combo['damage'],math.floor(base['damage']*combo['factor']+.5))
        profile['type']='ranged'
        self.assertLess(s.resolve(data)[0]['factor'],combo['factor'])
    def test_reject_invalid_references_and_bounds(self):
        for mutate in [lambda d:d['skills'][0].update(duration=float('nan')),lambda d:d['skills'][0].update(tick=0),lambda d:d['skills'][0].update(cooldown=1),lambda d:d['skilledMonsters'][0]['skills'][0].update(skillId='missing'),lambda d:d['skilledMonsters'][0]['skills'][0].update(downgrade=1),lambda d:d['skilledMonsters'][0]['skills'][0].update(trigger='expired'),lambda d:d['skilledMonsters'][0]['skills'].append(deepcopy(d['skilledMonsters'][0]['skills'][0])),lambda d:d['test'].update(skilledEnabled=1)]:
            d=deepcopy(self.data);mutate(d)
            with self.assertRaises(ValueError): b.validate(d)
    def test_silence_is_not_basic_attack_penalty(self):
        silence=next(x for x in self.data['skills'] if x['effect']=='silence')
        self.assertEqual(s.budget(silence,self.data['monsters'][0]),0)
        attack=read('src/server/combat/AttackService.luau')
        self.assertNotIn('SkillSilenced',attack)
        self.assertIn('SkillStunned',attack)
        self.assertIn('pending.stunEpoch',attack)
        self.assertIn('session.stunEpoch',attack)
    def test_runtime_and_ui_contracts(self):
        effects=read('src/server/combat/SkillEffects.luau');self.assertIn('Damage.Apply(source,target,amount,false,true)',effects)
        self.assertIn('state[effect] and not canRefresh then return false',effects)
        self.assertIn('active[target] ~= state',effects)
        self.assertIn('Effects.CanCast(model)',read('src/server/monster/MonsterSkills.luau'))
        self.assertNotIn('Skills.OnHit',read('src/server/monster/MonsterAttackExecutor.luau'))
        self.assertIn('Special.TryBegin',read('src/server/monster/MonsterAttackExecutor.luau'))
        self.assertIn('Effects.Apply(model,victim,skill',read('src/server/monster/MonsterSkillCast.luau'))
        self.assertIn('SkillMoveMultiplier',read('src/client/character/MovementController.luau'))
        self.assertIn('t.y + 1024',read('src/server/dev/GameplayTestLoadout.luau'))
        self.assertIn('Skilled · GP',read('src/server/dev/GameplayTestLayout.luau'))
        self.assertIn('skilled-monsters-editor',read('system/control-center/static/skill-editor.js'))
        self.assertIn('resolvedSkilledMonsters',read('system/control-center/api/balance.py'))

if __name__=='__main__':unittest.main()
