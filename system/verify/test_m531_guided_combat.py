"""M531 data math, guided authority and procedural presentation contracts."""
import json
from copy import deepcopy
from pathlib import Path
import sys, unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'system/control-center'))
from services import game_balance as b, skill_balance as s
from kanban_store import KanbanStore

def src(path): return (ROOT/path).read_text(encoding='utf-8')

class GuidedCombat(unittest.TestCase):
    def setUp(self): self.data=b.load()
    def test_run_speed_owned_by_database(self):
        self.assertIn('baseRunSpeed',self.data['rules'])
        for row in self.data['monsters']: self.assertGreater(row['runSpeed'],0)
        for profile in s.resolve(self.data):
            base=next(r for r in self.data['monsters'] if r['id']==profile['baseId'])
            self.assertEqual(profile['runSpeed'],base['runSpeed'])
        for key,value in [('baseRunSpeed',0),('monsterCastSeconds',float('nan'))]:
            d=deepcopy(self.data);d['rules'][key]=value
            with self.assertRaises(ValueError): b.validate(d)
        d=deepcopy(self.data);d['monsters'][0]['runSpeed']=401
        with self.assertRaises(ValueError): b.validate(d)
        self.assertIn('Balance.Rules.baseRunSpeed',src('src/server/character/CharacterStatsService.luau'))
        self.assertIn('if balance then balance.runSpeed',src('src/server/monster/MonsterInitialAttributes.luau'))
    def test_downgrade_cost_and_toggle(self):
        d=deepcopy(self.data); profile=d['skilledMonsters'][0]; profile['skills']=[{'skillId':'skill_poison','downgrade':True,'trigger':'cast','hpBelow':50}]
        row=s.resolve(d)[0]; base=next(r for r in d['monsters'] if r['id']==row['baseId']); skill=next(k for k in d['skills'] if k['id']=='skill_poison')
        raw=s.budget(skill,base,d['rules']['critMultiplier']); net=max(0,raw-d['rules']['monsterCastSeconds']/skill['cooldown'])
        self.assertAlmostEqual(row['factor'],1/(1+net)); self.assertLessEqual(row['damage'],base['damage'])
        profile['skills'][0]['downgrade']=False; self.assertEqual(s.resolve(d)[0]['damage'],base['damage'])
        profile['skills'][0]['trigger']='hit'
        with self.assertRaises(ValueError): b.validate(d)
    def test_matrix_inputs_and_server_boundaries(self):
        self.assertEqual({w['type'] for w in self.data['weapons'] if w['level']==30},set(b.TYPES))
        self.assertEqual({m['type'] for m in self.data['monsters'] if m['level']==30},{'melee','ranged'})
        for p in self.data['skilledMonsters']:
            self.assertTrue(any(m['type']==p['type'] and m['level']==p['level'] for m in self.data['monsters']))
        plan=src('src/server/dev/GameplayGuidedPlan.luau');self.assertIn('for i=1,3',plan);self.assertIn('distance=36',plan)
        service=src('src/server/dev/GameplayTestService.luau')
        for token in ['Report.Begin(s.player,character,models[1],stage)','Report.Emit(g.results,RuntimeVersion.Version)','if s.guide then return result(false','not allowed(player)','Report.Outcome() or "interrupted"','GameplayGuideTrial']:
            self.assertIn(token,service)
        damage=src('src/server/combat/DamageService.luau');self.assertLess(damage.index('Report.Damage(attacker, target, hp - newHP'),damage.index('target:SetAttribute("HP", newHP)'))
        report=src('src/server/dev/GameplayCombatReport.luau')
        for token in ['RunService:IsStudio()','GP_REPORT_BEGIN','GP_REPORT_END','GP_SUMMARY','r.dealt/duration','cyclesWithoutContact','firstCenterInRangeSeconds','90 then return "timeout"']:
            self.assertIn(token,report)
    def test_cast_presentation_and_kanban(self):
        cast=src('src/server/monster/MonsterSkillCast.luau'); normal=src('src/server/monster/MonsterAttackExecutor.luau')
        self.assertNotIn('Skills.OnHit',normal);self.assertIn('Special.TryBegin',normal)
        for token in ['agent.attackSerial==serial','Target.CanBeginTargetedCast','Effects.CanCast(model)','Skills.Reserve','"atk_special"','Cast.Cancel(agent)']:
            self.assertIn(token,cast)
        visual=src('src/client/combat/StatusEffectVisuals.luau')
        for token in ['nextPoison=now+3','"spine_02"','"BleedDrop"','"RootMarker"','p.CanCollide=false','Color3.fromRGB(225,26,30)','Color3.fromRGB(141,17,19)','mouth.Rotation=90','restoreBoots()']:
            self.assertIn(token,visual)
        cards={x['id']:x for x in KanbanStore(ROOT).list_cards()['cards']}
        for i in range(25,31): self.assertIn(f'KBN-{i:04}',cards)
        self.assertNotEqual(cards['KBN-0025']['status'],'DONE')

if __name__=='__main__':unittest.main()
