from pathlib import Path
import shutil, subprocess, unittest
ROOT = Path(__file__).resolve().parents[2]
def read(p): return (ROOT/p).read_text(encoding='utf-8')
class RemotePlayerAttack(unittest.TestCase):
    def test_phase_math(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua: self.skipTest('Lua CLI unavailable')
        subprocess.run([lua,'system/verify/attack_presentation_m612.lua'],cwd=ROOT,check=True,timeout=15)
    def test_server_validates_before_publishing(self):
        s=read('src/server/combat/AttackService.luau')
        start=s.index('session.presentation = if not fallback')
        for text in ('allowedAttackDescriptor(character, clipId)', 'AttackSessionStore.IsCoolingDown(player, now)', 'if not beginBowRelease('):
            self.assertLess(s.index(text),start)
        self.assertIn('AttackPresentation.Clear(character)',s)
        self.assertIn('AttackPresentation.Bounce(character, active.presentation',s)
        state=read('src/server/combat/AttackPresentationState.luau')
        for token in ('Workspace:GetServerTimeNow()', 'descriptor.animationId', 'HttpService:JSONEncode(state)', 'character:SetAttribute(State.Attribute, nil)'):
            self.assertIn(token,state)
        self.assertNotIn('RemoteEvent',state)
    def test_observers_use_same_composer_not_local_aim(self):
        s=read('src/client/character/animation/AttackUpperBodyComposer.luau')
        for token in ('newComposer(true)', 'newComposer(false)', 'if ownsLocalAim then AimPoseController.StepAfterExternalPose(deltaTime) end', 'activeComposers[AttackUpperBodyComposer] = nil','activeComposers[AttackUpperBodyComposer] = { hold = holdPose, step = composePose }'):
            self.assertIn(token,s)
        self.assertEqual(s.count('RunService.PreSimulation:Connect'),1)
        self.assertEqual(s.count('RunService.PreAnimation:Connect'),1)
    def test_observer_lifecycle_and_phase(self):
        s=read('src/client/character/animation/RemotePlayerAttackController.luau')
        for token in ('player == Players.LocalPlayer', 'entry.generation == generation', 'entry.composer.End()', 'player.CharacterRemoving:Connect', 'Players.PlayerRemoving:Connect', 'entry.state.serial == state.serial', 'Phase.Resolve(state, Workspace:GetServerTimeNow())', 'entry.composer.SeekPhase', 'SkillStunned', 'EquippedWeaponBalanceId', 'state.endAt - Workspace:GetServerTimeNow()'):
            self.assertIn(token,s)
        for token in ('FireServer','RenderStepped','Heartbeat:Connect','PreSimulation:Connect',':PivotTo('): self.assertNotIn(token,s)
        self.assertIn('RemotePlayerAttackController',read('src/client/init.client.luau'))
