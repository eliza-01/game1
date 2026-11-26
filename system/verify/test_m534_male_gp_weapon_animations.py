"""GP policy integration; live assets and pose timing require Studio Play."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
def read(p): return (ROOT/p).read_text(encoding='utf8')
class MaleGPWeapons(unittest.TestCase):
    def test_scoped_borrowing_not_attack(self):
        policy=read('src/shared/dev/GameplayTestAnimationPolicy.luau')
        for token in ('RunService:IsStudio()', 'GameplayTestKind', '"human_male"', 'weaponSet == "2hs" or weaponSet == "dualswords"', 'slot ~= "attack"', 'return "1hs"', 'return weaponSet'):
            self.assertIn(token,policy)
        resolver=read('src/client/character/animation/AnimationResolver.luau')
        self.assertLess(resolver.index('weaponSet = TestPolicy.WeaponSet'),resolver.index('local weapon = profile.weapons'))
        service=read('src/server/dev/GameplayTestService.luau')
        self.assertLess(service.index('GP currently requires human_male'),service.index('Loadout.Set(player, selection)',service.index('local function enter')))
    def test_exact_models_and_no_dual_attack_substitution(self):
        equip=read('src/server/weapon/WeaponEquipService.luau')
        for token in ('TestPolicy.IsMaleTest(character)', '"newbie_slayer_01" else "newbie_sword_01"', 'row.weaponType == expected', 'findByStudioPath', 'if isDual then "dualswords" else attackMovement.animationSet', 'local left = weapon:Clone()', 'BoneModelMount.SocketFrame(leftBone, "weapon")', 'if isDual and not dualReady and not testId then'):
            self.assertIn(token,equip)
        self.assertNotIn('if dualReady then "dualswords" else "1hs"',equip)
        self.assertNotIn('WeaponEquipService.TestModel("sword")',equip)
    def test_authoritative_dual_timing_and_explicit_fallback(self):
        plan=read('src/shared/combat/MeleeHitPlan.luau')
        self.assertNotIn('testPreview',plan)
        self.assertIn('time >= last.time',plan)
        client=read('src/client/character/animation/CharacterAnimationController.luau')
        server=read('src/server/combat/AttackService.luau')
        self.assertIn('HitPlan.Resolve(timeline, isDual)',client)
        self.assertIn('MeleeHitPlan.Resolve(timing, isDual)',server)
        self.assertIn('weaponSet == "2hs" and GameplayFallback.Allowed(character)',server)
        self.assertIn('clipId = GameplayFallback.ClipId',client)
        self.assertIn('if not fallback or previewAuthored then',client)
        self.assertIn('fallback and descriptor ~= nil and TestPolicy.BorrowsLocomotion',client)
        report=read('src/server/dev/GameplayCombatReport.luau')
        self.assertIn('animationPreview=TestPolicy.BorrowsLocomotion',report)
        self.assertIn('locomotionSet=TestPolicy.WeaponSet',report)
        self.assertIn('if row.timingOnly then key..="/timing-only"',report)
