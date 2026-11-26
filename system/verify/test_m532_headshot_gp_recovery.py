"""M532 static wiring; actual geometry/timing and GUI need Studio Play."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
def src(p): return (ROOT/'src'/p).read_text(encoding='utf-8')
class HeadshotGP(unittest.TestCase):
    def test_headshot_never_adds_victim(self):
        s=src('server/combat/AttackDamageResolver.luau')
        self.assertIn('MeleeTargetQuery.Find(character, root, query.attackRange,',s)
        self.assertIn('if #targets > 0 then',s)
        self.assertEqual(s.count('EntityHitboxService.RaycastAimRegions('),1)
        self.assertIn('rayStart, rayDirection, Config.MeleeHeadshotRayDistance)',s)
        self.assertIn('MeleeHeadshotRayDistance = 32',src('shared/combat/AttackConfig.luau'))
        self.assertNotIn('HitWithinAttackRadius',s)
        self.assertIn('MeleeTargetQuery.IsUnobstructed',s)
        self.assertIn('contact.model == aimed.model',s)
        self.assertIn('aimedHead.model == model',s)
        self.assertIn('Aim.HitWithinAttackRadius',src('server/combat/AttackFeedbackTargeting.luau'))
    def test_fallback_authority(self):
        f=src('shared/combat/GameplayAttackFallback.luau')
        for t in ['RunService:IsStudio()','GameplayTestKind','kind == "bigsword"','Cadence.DurationForStat','HitEnd={time=duration*0.8}','HitFirst = {time=duration*0.4}']:
            self.assertIn(t,f)
        self.assertNotIn('"bow"',f)
        s=src('server/combat/AttackService.luau'); c=src('client/character/animation/CharacterAnimationController.luau')
        for t in ['GameplayFallback.Allowed(character)','if fallback then timing = GameplayFallback.Resolve(character) end','MeleeHitPlan.Resolve(timing','AttackSessionStore.IsCoolingDown','scheduleMeleeArc']:
            self.assertIn(t,s)
        self.assertIn('and character:GetAttribute("Game1GameplayTestOwner") == player.UserId',s)
        self.assertIn('if slot == "attack" and GameplayFallback.Allowed(character) then return nil end',src('client/character/animation/AnimationResolver.luau'))
        self.assertIn('timeline = GameplayFallback.Resolve(character)',c)
        self.assertIn('clipId = GameplayFallback.ClipId',c)
        self.assertIn('if fallback then',c)
        self.assertIn('GP timing-only fallback',c)
    def test_export_does_not_reset(self):
        s=src('server/dev/GameplayTestService.luau'); c=src('client/dev/GameplayTestController.luau')
        export=s.split('if action == "guideExport" then',1)[1].split('if action == "guideRetry"',1)[0]
        self.assertIn('Report.Emit(g.results,RuntimeVersion.Version.." PARTIAL")',export)
        for t in ['clearGroup','g.running','s.guide=nil','table.remove']:
            self.assertNotIn(t,export)
        for t in ['guideExport','guideRetry','guideSkip']:
            self.assertIn(t,c)
        self.assertIn('Report.EmitRetry(#g.results)',s)
        self.assertIn('table.remove(g.results)',s)
        self.assertIn('elseif not g.pending and #g.results>0 then',s)
        self.assertIn('g.pending=true',s)
        self.assertIn('outcome="skipped",reason="manual_skip"',s)
        self.assertIn('Report.EmitTrial(#s.guide.results,row)',s)
    def test_report_labels(self):
        r=src('server/dev/GameplayCombatReport.luau')
        for t in ['GP_TRIAL]','GP_TRIAL_RETRY]','if row.outcome=="skipped" then continue end','/timing-only','/animation-preview','fallbackAttacks','firstCenterInRangeSeconds','playerRunStudsPerSecond','monsterRunStudsPerSecond']:
            self.assertIn(t,r)
        self.assertNotIn('firstInRangeSeconds=',r)
if __name__=='__main__': unittest.main()
