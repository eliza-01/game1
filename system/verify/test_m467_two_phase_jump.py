"""M467: accepted jump impulse -> start -> loop -> grounded locomotion.

Contract tests for the local Roblox ControllerManager and animation client.
Roblox AnimationTrack event timing still requires Studio Play acceptance.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


def source(path):
    return (ROOT / path).read_text(encoding='utf-8')


class TwoPhaseJumpContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.movement = source('src/client/character/MovementController.luau')
        cls.animation = source('src/client/character/animation/CharacterAnimationController.luau')
        cls.resolver = source('src/client/character/animation/AnimationResolver.luau')
        cls.catalog = source('system/control-center/animation_core/common.py')

    def test_authoring_slots_are_still_separate_and_published_only(self):
        for slot, looped in [('jump_start', 'False'), ('jump_loop', 'True')]:
            self.assertRegex(self.catalog, rf'"slot": "{slot}"[^\n]*"looped": {looped}')
        self.assertIn('"base_jump_start": "jump_start"', self.catalog)
        self.assertIn('"base_jump_loop": "jump_loop"', self.catalog)
        self.assertIn('return AnimationResolver.Resolve(character, "base", nil, slot)', self.resolver)
        self.assertIn('AnimationResolver.ListForCharacter(newCharacter)', self.animation)
        self.assertNotIn('"base_jump"', self.catalog)

    def test_only_successful_physical_impulse_initiates_start(self):
        m = self.movement
        self.assertIn('newCharacter:SetAttribute("AnimationAirborne", false)', m)
        self.assertIn('newCharacter:SetAttribute("AnimationJumpSequence", 0)', m)
        fn = m[m.index('local function performJump()'):m.index('local function updateJumpDescent()')]
        impulse = fn.index('navigationRoot:ApplyImpulse(')
        seq = fn.index('character:SetAttribute("AnimationJumpSequence",')
        airborne = fn.index('character:SetAttribute("AnimationAirborne", true)')
        self.assertLess(impulse, seq)
        self.assertLess(seq, airborne)
        self.assertIn('if deltaVelocity > 0 then', fn)
        self.assertIn('if not isGrounded() or os.clock() < airLockUntil or jumpInFlight then', fn)
        self.assertNotIn('AnimationAirborne', m[m.index('function MovementController.RequestJump()'):])

    def test_grounding_and_death_release_airborne_flag(self):
        m = self.movement
        descent = m[m.index('local function updateJumpDescent()'):m.index('local function updateMovement(')]
        self.assertIn('jumpInFlight and isGrounded() and os.clock() >= airLockUntil', descent)
        self.assertGreaterEqual(descent.count('character:SetAttribute("AnimationAirborne", false)'), 2)
        self.assertIn('character:SetAttribute("AnimationAirborne", false)', m[m.index('local function updateMovement('):])
        self.assertIn('updateJumpDescent()', m[m.index('if UserInputService:GetFocusedTextBox() then'):])

    def test_two_phase_playback_and_cleanup(self):
        a = self.animation
        self.assertIn('"AnimationAirborne", "AnimationJumpSequence"', a)
        self.assertIn('if airborneSequence ~= sequence then', a)
        self.assertIn('slot = if jumpStartFinished then "jump_loop" else "jump_start"', a)
        self.assertIn('local descriptor = AnimationResolver.ResolveLocomotion(character, slot)', a)
        self.assertIn('jumpStartStoppedConnection = boundTrack.Stopped:Connect(function()', a)
        self.assertIn('jumpStartFinished = true\n\t\t\trefreshLoop()', a)
        self.assertIn('boundCharacter:GetAttribute("AnimationAirborne") ~= true', a)
        self.assertIn('currentLoop ~= boundTrack', a)
        self.assertIn('if airborneSequence ~= -1 then', a)
        self.assertIn('disconnectJumpStart()', a[a.index('local function clearCharacter()'):a.index('local function findAnimator(')])
        self.assertIn('disconnectJumpStart()', a[a.index('local function stopCurrentLoop('):a.index('local function stopCurrentAction(')])
        self.assertNotIn('HumanoidStateType.Jumping', a)

    def test_missing_start_falls_back_to_loop_without_fake_asset(self):
        a = self.animation
        self.assertIn('if inJump and not descriptor and slot == "jump_start" then', a)
        self.assertIn('slot = "jump_loop"', a)
        self.assertIn('if inJump and not descriptor then', a)
        self.assertIn('[game1][animation][jump] jump_start missing', a)
        self.assertIn('[game1][animation][jump] jump_loop missing', a)
        self.assertIn('if inJump and slot == "jump_start" then', a)
        self.assertNotIn('rbxassetid://0', a)


if __name__ == '__main__':
    unittest.main()
