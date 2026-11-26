"""One-time compensation, independent character bonus, unchanged damage path."""
from pathlib import Path
from fractions import Fraction
import math, sys, unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'system/control-center'))
from services import game_balance as b
BASE_HP = {'melee': [96, 102, 108, 120, 126, 138, 144, 150, 162, 300, 318, 342, 360, 372, 384, 396, 414, 426, 438, 576, 600, 624, 648, 672, 696, 714, 738, 762, 786, 900, 936, 972, 1014, 1050, 1086], 'ranged': [106, 112, 119, 132, 139, 152, 158, 165, 178, 330, 350, 376, 396, 409, 422, 436, 455, 469, 482, 634, 660, 686, 713, 739, 766, 785, 812, 838, 865, 990, 1030, 1069, 1115, 1155, 1195]}
class CharacterATK(unittest.TestCase):
    def test_curve_and_fixed_monster_hp(self):
        d=b.load(); weapons=d['weapons']; grades=sorted({w['level'] for w in weapons})
        cumulative=0; step=100
        for row in d['levels']:
            l=row['level']
            if l>1:
                if l>2:
                    low,high=next((a,z) for a,z in zip(grades,grades[1:]) if a<=l-1<z)
                    prev={w['type']:w['damage'] for w in weapons if w['level']==low}
                    nxt={w['type']:w['damage'] for w in weapons if w['level']==high}
                    common=prev.keys()&nxt.keys()
                    growth=sum((Fraction(nxt[k],prev[k])-1 for k in common),Fraction(0))/len(common)/(high-low)
                    step=math.floor(step*(1+growth)+Fraction(1,2))
                cumulative+=step
            self.assertEqual(row['attackBonus'],cumulative/100)
            types={w['type'] for w in weapons if w['level']<=l}
            attacks=[d['rules']['baseDamage']+max((w for w in weapons if w['type']==k and w['level']<=l),key=lambda w:w['level'])['damage'] for k in types]
            ratio=sum((Fraction(a+cumulative//100,a) for a in attacks),Fraction(0))/len(attacks)
            for m in (m for m in d['monsters'] if m['level']==l):
                old=BASE_HP[m['type']][l-1]
                self.assertEqual(m['hp'],math.floor(old*ratio+Fraction(1,2)))
                for attack in attacks:
                    # Average compensation cannot exactly preserve every weapon's TTK.
                    self.assertLessEqual(abs(m['hp']*attack/(old*(attack+cumulative//100))-1),.13)
    def test_no_target_scaling(self):
        balance=(ROOT/'src/shared/balance/Balance.luau').read_text()
        damage=(ROOT/'src/server/combat/DamageService.luau').read_text()
        self.assertIn('Registry.rules.baseDamage + Balance.Level(level).attackBonus',balance)
        self.assertIn('math.max(0, hp - finalDamage)',damage)
        self.assertNotIn('MonsterHealthScale',damage)
        self.assertNotIn('AttackScaleAt',balance)
