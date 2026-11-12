"""M310 presentation contract: bow reuses the hands camera and facing mechanics.

These are static integration tests; camera feel and transformed Bone poses must
still be verified in a Studio client Play session.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]

def src(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")

class HandsBowCameraParity(unittest.TestCase):
    def test_one_camera_controller_handles_rmb_for_all_weapons(self):
        camera = src("src/client/character/CameraController.luau")
        movement = src("src/client/character/MovementController.luau")
        self.assertIn("UserInputService.MouseBehavior = Enum.MouseBehavior.LockCurrentPosition", camera)
        self.assertIn("CharacterConfig.InputBindings.CameraOrbit[1]", camera)
        self.assertIn("UserInputService:GetMouseDelta()", camera)
        self.assertIn('"game1CustomCamera"', camera)
        self.assertNotIn("bowEquipped", movement)
        self.assertNotIn('GetAttribute("AnimationWeaponSet")', movement)
        self.assertIn("controllerManager.FacingDirection = moveDirection", movement)
        self.assertIn("backwardActive and backwardRelativeDirection", movement)
        self.assertIn("backwardCameraSteering", movement)

    def test_stationary_attacks_reuse_shared_root_compensation(self):
        attack = src("src/client/combat/AttackController.luau")
        movement = src("src/client/character/MovementController.luau")
        self.assertIn("if movementController and not movingAtAttackStart then", attack)
        self.assertNotIn("not movingAtAttackStart and not isBow", attack)
        self.assertIn("movementController.BeginAimFacingCompensation(", attack)
        self.assertIn("movementController.UpdateAimFacingCompensation(direction.Unit)", attack)
        self.assertIn("movementController.UpdateAimFacingCompensation(direction)", attack)
        self.assertIn("function MovementController.EndAimFacingCompensation()", movement)
        self.assertIn("clearAimFacingCompensation()", movement)
        self.assertIn("if aimFacingActive and not movementLocked and moveDirection.Magnitude > 0.001 then", movement)

    def test_bow_torso_aim_only_while_attacking(self):
        pose = src("src/client/combat/AimPoseController.luau")
        self.assertIn("local bowAttack = activeAttack and character ~= nil", pose)
        self.assertIn('GetAttribute("EquippedWeaponType")', pose)
        self.assertIn("local _, aimDirection = CameraController.GetAimRay()", pose)
        self.assertIn("target = currentRoot.Position + aimDirection * 100", pose)
        self.assertIn("StepAfterExternalPose(deltaTime)", src("src/client/character/animation/AttackUpperBodyComposer.luau"))
        self.assertIn("if not target then return 0, 0, false end", pose)
        self.assertIn("pitchRotation * yawRotation * animatedRotation", pose)

    def test_bow_release_melee_timeline_and_server_remain_independent(self):
        attack = src("src/client/combat/AttackController.luau")
        self.assertIn("local damageWindow = if isBow then nil else CharacterAttackWindow.Resolve(action.timeline)", attack)
        self.assertIn("BowProjectileConfig.ReleaseEvent", attack)
        self.assertIn("BowProjectileConfig.AimUpdateInterval", attack)
        self.assertIn("bowAimRemote:FireServer({", attack)
        self.assertIn("weaponPoseRemote:FireServer({", attack)
        self.assertIn("movementController.EndAimFacingCompensation()", attack)

if __name__ == "__main__":
    unittest.main()
