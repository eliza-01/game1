"""M153: Spawn sockets carry heading; custom characters must stay world-upright.

The numeric examples below come from the Roblox Studio Bone audit of the
house_level4_01 authoring rig. Runtime execution still needs Studio Play.
"""
from pathlib import Path
from math import hypot, isclose
import unittest

ROOT = Path(__file__).resolve().parents[2]


def read(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


def project_horizontal(v):
    horizontal_length = hypot(v[0], v[2])
    return None if horizontal_length < 1e-4 else (v[0] / horizontal_length, 0, v[2] / horizontal_length)


class HouseSpawnOrientationM153(unittest.TestCase):
    def test_bone_spawn_heading_faces_tail_to_head(self):
        # House bone +Y is Blender Head -> Tail; facing must use -Y (Tail -> Head).
        # The imported -Z/LookVector is vertical, so passing the whole CFrame
        # to a character erroneously leaves that character lying down.
        bone = {
            "house_floor_01_spawn_01_socket": (-0.0000018813214, 0.0001307529, 1.0),
            "house_floor_02_spawn_01_socket": (-0.0000018813214, 0.0001307529, 1.0),
            "land_spawn_01_socket": (0.0000018813213, -0.0001307529, -1.0),
        }
        for name, bone_y in bone.items():
            with self.subTest(name=name):
                forward = project_horizontal(tuple(-x for x in bone_y))
                self.assertIsNotNone(forward)
                self.assertTrue(isclose(forward[1], 0))
                self.assertTrue(isclose(hypot(forward[0], forward[2]), 1, rel_tol=1e-6))
                self.assertGreater(abs(forward[2]), 0.9999)
                self.assertLess(forward[2] * bone_y[2], -0.9999)

    def test_vertical_axis_is_rejected_not_reinterpreted(self):
        self.assertIsNone(project_horizontal((0.0, 1.0, 0.0)))
        self.assertIsNone(project_horizontal((0.0, -1.0, 0.0)))

    def test_shared_projection_keeps_world_up_and_separates_bone_and_attachment(self):
        source = read("src/shared/world/HouseSpawnOrientation.luau")
        self.assertIn("if fromBone then -socketFrame.UpVector else socketFrame.LookVector", source)
        self.assertIn("Vector3.new(authoredForward.X, 0, authoredForward.Z)", source)
        self.assertIn("CFrame.lookAlong(position, horizontalForward / magnitude, WORLD_UP)", source)
        self.assertIn("WORLD_UP = Vector3.yAxis", source)
        self.assertIn("if magnitude < MIN_FORWARD_LENGTH then", source)
        self.assertIn("return nil", source)
        self.assertNotIn("CFrame.Angles(math.rad(90)", source)
        self.assertNotIn("then socketFrame.UpVector else", source)

    def test_server_uses_upright_heading_without_touching_other_socket_uses(self):
        service = read("src/server/world/HouseSocketService.luau")
        method = service.split("function Service.TeleportDebug", 1)[1].split("function Service.Start", 1)[0]
        self.assertIn('SpawnOrientation.Upright(getFrame(socket), socket:IsA("Bone"), 3)', method)
        self.assertIn("character:PivotTo(targetFrame)", method)
        self.assertIn('character:FindFirstChildOfClass("ControllerManager")', method)
        self.assertIn("controller.FacingDirection = targetFrame.LookVector", method)
        self.assertNotIn("character:PivotTo(getFrame(socket)", method)
        self.assertIn("root.AssemblyLinearVelocity = Vector3.zero", method)
        self.assertIn("root.AssemblyAngularVelocity = Vector3.zero", method)
        self.assertIn('definition.role ~= "spawn"', method)
        self.assertIn("Service.FindNearest(player, name)", method)

    def test_runtime_root_and_door_are_not_changed(self):
        rig = read("src/server/character/CharacterRigService.luau")
        door = read("src/server/world/HouseDoorService.luau")
        self.assertIn("controllerManager.UpDirection = Vector3.yAxis", rig)
        self.assertIn("character.PrimaryPart = root", rig)
        self.assertIn("door:PivotTo(frame)", door)


if __name__ == "__main__":
    unittest.main()
