"""M654 source contracts and actual transition functions against deterministic Lua doubles.
Native AnimationTrack replication/rendering must still be checked in published Play.
"""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
ANIM = ROOT / 'src/client/character/animation'


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


class AnimationReliability(unittest.TestCase):
    def test_handoff_waits_for_loaded_successor_and_never_natural_stop(self):
        ctrl = (ANIM / 'CharacterAnimationController.luau').read_text('utf-8')
        life = ctrl.split('local function stepLifeRequest()', 1)[1].split('local function maintainDeathTerminalPose', 1)[0]
        self.assertLess(life.index('cache:IsLoaded(track)'), life.index('DeathAnimationPolicy.Start(track,'))
        self.assertLess(life.index('DeathAnimationPolicy.Start(track,'), life.index('stopCurrentLoop(0)'))
        self.assertNotIn('.Stopped:', ctrl.split('local function playBaseLifeAction', 1)[1].split('local function bindCharacter', 1)[0])
        maintain = ctrl.split('local function maintainDeathPose', 1)[1].split('local function bindCharacter', 1)[0]
        self.assertLess(maintain.index('LatchVisibleTerminalPose(reviveTrack'), maintain.index('notifyReviveAnimationFinished(boundCharacter'))
        loop = ctrl.split('local nextTrack = cache:Get(descriptor)', 1)[1].split('local function notifyDeathTerminalReached', 1)[0]
        self.assertLess(loop.index('cache:IsLoaded(nextTrack)'), loop.index('nextTrack:Play(0, 1, playbackScale)'))
        self.assertLess(loop.index('nextTrack:Play(0, 1, playbackScale)'), loop.index('releaseLifeHold()'))
        self.assertIn('and currentLoop.IsPlaying then', ctrl)
        self.assertIn('if not existing.track.IsPlaying then applyDescriptor', (ANIM / 'AnimationTrackCache.luau').read_text('utf-8'))

    def test_replication_and_curtain_lifetime(self):
        ctrl = (ANIM / 'CharacterAnimationController.luau').read_text('utf-8')
        self.assertEqual(ctrl.count('AnimationTrackCache.new(animator)'), 1)
        self.assertEqual(ctrl.count('RunService.PreAnimation:Connect('), 1)
        self.assertIn('if not cache and now >= nextAnimatorProbe then', ctrl)
        self.assertIn('if localPlayer.Character ~= newCharacter or character == newCharacter then return end', ctrl)
        self.assertIn('if character ~= newCharacter or cache ~= boundCache then return end', ctrl)
        self.assertNotIn('if character == model and not animator then return false end', ctrl)
        self.assertIn('event:FireServer(boundCharacter)', ctrl)
        self.assertIn('remote:FireServer(boundCharacter, visualReady)', ctrl)
        service = read('src/server/character/CharacterService.luau')
        self.assertIn('if reportedCharacter ~= character or not character.Parent', service)
        self.assertIn('if not character or character ~= reportedCharacter or not character.Parent', service)
        self.assertIn('if visualReady ~= true then', service)
        ui = read('src/client/character/DeathRespawnController.luau')
        self.assertLess(ui.index('beginCover(requestCharacter)'), ui.index('remote:InvokeServer()'))
        self.assertIn('character == awaitingReplacement', ui)
        self.assertIn('if coverGeneration ~= ticket then return end', ui)
        self.assertIn('if character:GetAttribute("RevivePoseReady") == true then endCover() end', ui)

    def test_transition_functions_and_terminal_policy_in_lua(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua:
            self.skipTest('Standalone Lua unavailable; native Roblox still required')
        ctrl = (ANIM / 'CharacterAnimationController.luau').read_text('utf-8')
        code = ctrl[ctrl.index('local function releaseLifeHold()'):ctrl.index('local function bindCharacter')]
        # Adapt syntax only; Roblox objects, time, scheduler and animator are doubles.
        code = re.sub(r': (?:Model|AnimationTrack|number|string|boolean)\??(?=[,)\n])', '', code)
        code = code.replace('): boolean', ')')
        code = code.replace('slot = if jumpStartFinished then "jump_loop" else "jump_start"', 'slot = jumpStartFinished and "jump_loop" or "jump_start"')
        code = code.replace('if isJumpSlot then 0.05 else 0.15', '(isJumpSlot and 0.05 or 0.15)')
        code = code.replace('if state == "DeathIdle" then track.Length / math.max(0.01, track.Speed) else deltaTimeSim', '(state == "DeathIdle" and track.Length / math.max(0.01, track.Speed) or deltaTimeSim)')
        policy = read('src/shared/combat/DeathAnimationPolicy.luau')
        policy = re.sub(r': (?:AnimationTrack|number)\??(?=[,)\n])', '', policy).replace(': (boolean, number?)', '')
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d/'policy.lua').write_text(policy, encoding='utf-8')
            (d/'functions.lua').write_text(code, encoding='utf-8')
            subprocess.run([lua, str(ROOT/'system/verify/animation_reliability_m654.lua'), str(d/'policy.lua'), str(d/'functions.lua')], check=True, timeout=15)


if __name__ == '__main__':
    unittest.main()
