"""M533 canonical data and targeted-cast/presentation integration contracts."""
import unittest, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'system/control-center'))
from services import game_balance as b, skill_balance as s

def read(path): return (ROOT/path).read_text(encoding='utf8')

class TargetedStatus(unittest.TestCase):
    def test_durations_and_generated_downgrade(self):
        data=b.load(); rows={x['effect']:x for x in data['skills']}
        self.assertEqual({k:rows[k]['duration'] for k in ('poison','bleed','slow','root','silence','stun')},dict(poison=10,bleed=10,slow=10,root=5,silence=5,stun=3))
        self.assertEqual(rows['slow']['power'],30)
        for effect in ('poison','bleed'):
            self.assertEqual(rows[effect]['duration']/rows[effect]['tick'],10)
        for r in s.resolve(data):
            base=next(x for x in data['monsters'] if x['id']==r['baseId'])
            expected={'skilled_poison':72,'skilled_bleed':74,'skilled_slow':80,'skilled_root':70,'skilled_stun':69,'skilled_silence':84,'skilled_might':81,'skilled_haste':81}
            if r['id'] in expected: self.assertEqual(r['damage'],expected[r['id']])
            self.assertEqual((r['hp'],r['xp'],r['gold'],r['runSpeed']),(base['hp'],base['xp'],base['gold'],base['runSpeed']))
        self.assertEqual(b.render(data),b.OUTPUT.read_text(encoding='utf8'))
    def test_cast_commits_without_basic_hit_test(self):
        cast=read('src/server/monster/MonsterSkillCast.luau'); start,commit=cast.split('local committed=false',1)
        self.assertIn('Target.CanBeginTargetedCast(agent,target)',start)
        self.assertIn('Target.IsValid(target) and Target.AllowsTarget(agent,target) and Effects.CanCast(model)',start)
        self.assertIn('agent.specialCast==cast and agent.target==target',start)
        self.assertIn('while valid() do',commit); self.assertIn('Effects.Apply(model,victim,skill',commit)
        self.assertNotIn('AttackStillConnects',cast); self.assertNotIn('CanBeginTargetedCast',commit)
        normal=read('src/server/monster/MonsterAttackExecutor.luau'); self.assertIn('TargetPolicy.AttackStillConnects(agent, target)',normal)
        policy=read('src/server/monster/MonsterTargetPolicy.luau'); begin,hit=policy.split('local function attackStillConnects',1)
        self.assertIn('withinAttackRange(agent, target) and hasLineOfSight(agent, target)',begin)
        # M536 removes only the normal hit's facing gate, not range/LOS.
        self.assertIn('if not withinAttackRange(agent, target) then return false end',hit)
        self.assertIn('return hasLineOfSight(agent, target)',hit)
        self.assertNotIn('ATTACK_ARC_DEGREES',hit)
    def test_visual_and_stun_lifecycle_contract(self):
        visual=read('src/client/combat/StatusEffectVisuals.luau')
        for token in ['cloud=Instance.new("Attachment")','cloud.Parent=root','smoke.LockedToPart=true','PointToObjectSpace(bonePoint(character,root))','Color3.fromRGB(190,130,240)','NumberSequenceKeypoint.new(1,8)','if cloud then cloud:Destroy() end']:
            self.assertIn(token,visual)
        controller=read('src/client/character/animation/CharacterAnimationController.luau')
        stun=controller.split('if character:GetAttribute("SkillStunned") == true then',1)[1].split('local slot = movementSlot()',1)[0]
        for token in ['stopCurrentAction(0.06)','SocialAnimationPlayback.Resolve(character, "unaware")','track.Looped = true','elseif currentActionSlot == "stun" then','stopCurrentAction(0.1)']:
            self.assertIn(token,stun)
        self.assertIn('local refreshAttributes = { "SkillStunned"',controller)
        action=controller.split("function CharacterAnimationController.PlayAction",1)[1]
        self.assertIn('if character:GetAttribute("SkillStunned") == true then return nil end',action)
        self.assertIn('human_common__social__unaware__01',read('src/shared/character/CharacterAnimationRegistry.luau'))
        attack=read('src/client/combat/AttackController.luau');self.assertIn('or playerCharacter:GetAttribute("SkillStunned") == true',attack)

if __name__=='__main__': unittest.main()
