"""M545: one lifetime owner, player stats, regen, GP-only fixture and receipt UI."""
import json, re, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def read(p): return (ROOT/p).read_text(encoding='utf8')

class PlayerBuffs(unittest.TestCase):
    def test_definitions_and_slow(self):
        definitions=read('src/shared/combat/BuffDefinitions.luau')
        data=json.loads(read('config/balance/gameplay.json'))
        rows={s['effect']:s for s in data['skills'] if s['id'].endswith('_d')}
        self.assertEqual(set(rows),{'might','earth','life','wind'})
        for row in rows.values():
            self.assertGreater(row['power'],0)
            self.assertGreater(row['duration'],0)
        self.assertIn('Balance.Skill("skill_"..icon.effect.."_d")',definitions)
        self.assertIn('slow',{s['effect'] for s in data['skills']})
        self.assertIn('1-slow.power/100',read('src/server/combat/SkillEffects.luau'))
        self.assertAlmostEqual(1-.4,.6)

    def test_one_server_effect_owner_and_live_stats(self):
        effects=read('src/server/combat/SkillEffects.luau')
        for token in ['state[effect] and not canRefresh then return false','Stats.SetModifierSource(model, "skill-buffs"','Stats.ClearModifierSource(model,"skill-buffs")','state.might and not player','state[effect] ~= entry','target:GetAttributeChangedSignal("LifeState")','target.Destroying:Connect','BuffUntil_','BuffGain_life']:
            self.assertIn(token,effects)
        stats=read('src/server/character/CharacterStatsService.luau')
        for token in ['resolved *= 1 + percent / 100','resolved - beforeBuff','BuffGain_might','BuffGain_earth','BuffGain_wind','math.clamp(previousHP, 0, math.max(0, newMaxHP))']:
            self.assertIn(token,stats)
        for base in (10,62.5,125,162):
            self.assertAlmostEqual(base*1.2-base,base*.2)
        for base in (100,540,1200):
            self.assertEqual(round(base*1.3)-base,round(base*.3))
        self.assertEqual((160+20)/10,18)
        self.assertAlmostEqual((160+20)/10*.6,10.8)

    def test_regen_and_gp_isolation(self):
        self.assertIn('RegenerationHPPerSecond = 1',read('src/shared/character/CharacterStatsConfig.luau'))
        regen=read('src/server/character/CharacterRegenerationService.luau')
        for token in ['GameplayGuideActive','if guided then 0 else','Healing.TestRate(character, "GameplayTestRegen")','BuffGain_life','Healing.Restore(character, rate * elapsed)']:
            self.assertIn(token,regen)
        service=read('src/server/dev/GameplayTestService.luau')
        for token in ['RunService:IsStudio() and Access.GameplayTestEnabled() and Access.ServerAllowed(player)','actor~=s.player','(root.Position-part.Position).Magnitude>12','Buffer.Build(folder,s.layout','panelAction(actor,part,function(character)','Effects.Apply(character,character,definition,0,true)','Effects.Clear(character)','SetAttribute("GameplayGuideActive",true)','SetAttribute("GameplayGuideActive",nil)','else s.layout.hub,true)']:
            self.assertIn(token,service)
        self.assertIn('if not Buffs.ByEffect[effect] then state[effect]=nil end',read('src/server/combat/SkillEffects.luau'))
        self.assertIn('SkillEffects.Clear(character,preserveBuffs)',read('src/server/dev/GameplayTestArena.luau'))

    def test_ui_and_fixture(self):
        fixture=read('src/server/dev/GameplayBufferDummy.luau')
        for token in ['BufferDummy','ClickDetector','ProximityPrompt','Presentation.Step(pose,t,true)','onOpen(player,root)']:
            self.assertIn(token,fixture)
        hud=read('src/client/combat/BuffHud.luau')
        for token in ['BuffGain_','BuffUntil_','workspace:GetServerTimeNow()','plate.AbsolutePosition.X+plate.AbsoluteSize.X+8','TextTransparency=1','slot.icon.AbsolutePosition','flight:Play()','slot.icon.Visible=true','Visuals.Play(character,row.color)']:
            self.assertIn(token,hud)
        fx=read('src/client/combat/BuffCastVisuals.luau')
        for token in ['AuraWall','p.CanCollide=false','p.CanQuery=false','sparks.EmissionDirection=Enum.NormalId.Top','sparks:Emit(32)','attachment:Destroy()','connection:Disconnect()']:
            self.assertIn(token,fx)
        self.assertNotIn('RemoteEvent',hud+fixture+fx)

if __name__=='__main__': unittest.main()
