"""M365: Fire uses Bone HEAD as origin and WORLD +Y as emission direction.

Source contracts and pure-rotation math; visual integration needs Studio Edit/Play.
"""
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def multiply(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3))
                       for j in range(3)) for i in range(3))


def transpose(a):
    return tuple(tuple(a[j][i] for j in range(3)) for i in range(3))


def rotation(x, y, z):
    c, s = math.cos, math.sin
    return multiply(multiply(((1, 0, 0), (0, c(x), -s(x)), (0, s(x), c(x))),
                             ((c(y), 0, s(y)), (0, 1, 0), (-s(y), 0, c(y)))),
                    ((c(z), -s(z), 0), (s(z), c(z), 0), (0, 0, 1)))


class BoneFireWorldUpContract(unittest.TestCase):
    def test_all_bone_rotations_compensate_to_world_up(self):
        for angles in ((0, 0, 0), (math.pi, 0, 0), (0, math.pi, 0),
                       (0, 0, math.pi), (math.pi / 2, 0, 0),
                       (0.37, 1.8, -2.4), (-1.4, 0.71, 2.8)):
            with self.subTest(angles=angles):
                bone = rotation(*angles)
                local = transpose(bone)  # inverse Bone world rotation
                world = multiply(bone, local)
                result = tuple(world[i][1] for i in range(3))
                for received, expected in zip(result, (0, 1, 0)):
                    self.assertAlmostEqual(received, expected, places=12)
                # Attachment local translation is zero: exactly at Bone head.
                head = (15.0, -2.0, 100.0)
                offset = (0.0, 0.0, 0.0)
                actual = tuple(head[i] + sum(bone[i][j] * offset[j]
                                             for j in range(3)) for i in range(3))
                self.assertEqual(actual, head)

    def test_client_runtime_owns_only_cosmetic_orientation(self):
        source = read("src/client/world/BoneFireController.luau")
        init = read("src/client/init.client.luau")
        self.assertIn('WaitForChild("BoneFireController")', init)
        self.assertIn('bone.TransformedWorldCFrame', source)
        self.assertIn('rotation:Inverse()', source)
        self.assertIn('state.anchor.CFrame = state.expectedLocalFrame', source)
        self.assertIn('if fire.Heat < 0 then fire.Heat = -fire.Heat end', source)
        self.assertIn('Workspace.DescendantAdded:Connect', source)
        self.assertIn('Workspace:GetDescendants()', source)  # one-time scan
        callback = source.split('RunService.Heartbeat:Connect(function(dt)', 1)[1].split('\n    end)\nend', 1)[0]
        self.assertNotIn('GetDescendants()', callback)
        self.assertIn('if count == 0 and connection then', source)
        self.assertIn('if tracked[fire]', source)
        self.assertIn('if current:IsA("BasePart") then return nil end', source)
        self.assertIn('if not current:IsA("Attachment") then return nil end', source)
        self.assertNotIn('Fire:Clone()', source)

    def test_plugin_authors_head_world_up_without_bone_edits(self):
        source = read("system/studio-plugin/fire-tuner/fire_bone.lua")
        self.assertIn('local FIRE_ANCHOR = "Game1FireDirection"', source)
        self.assertIn('bone.TransformedWorldCFrame.Rotation:Inverse()', source)
        self.assertIn('anchor.CFrame = bone.TransformedWorldCFrame.Rotation:Inverse()', source)
        self.assertIn('anchor:SetAttribute(FIRE_WORLD_UP, true)', source)
        self.assertIn('fire.Parent = anchor', source)
        self.assertIn('if fire.Heat < 0 then fire.Heat = -fire.Heat end', source)
        self.assertIn('Align existing Fire at Head (world up)', source)
        self.assertIn('ChangeHistoryService:TryBeginRecording(', source)
        self.assertIn('ChangeHistoryService:FinishRecording(', source)
        self.assertNotIn('axis.CFrame = CFrame.Angles(math.pi', source)
        self.assertNotIn('bone.CFrame =', source)
        self.assertNotIn('Bone.PivotOffset', source)

    def test_read_only_selection_and_explicit_migration(self):
        source = read("system/studio-plugin/fire-tuner/fire_bone.lua")
        selected = source.split('local function bindSelected()', 1)[1].split(
            'selectButton.MouseButton1Click', 1)[0]
        self.assertNotIn('placeFireAtHead(', selected)
        self.assertNotIn('createFire()', selected)
        self.assertNotIn('SetAttribute(', selected)
        self.assertIn('RunService:IsEdit()', source)
        self.assertIn('axis:GetAttribute(FIRE_WORLD_UP) == true', source)
        self.assertIn('currentBone.TransformedWorldCFrame.Rotation:Inverse()', source)
        self.assertIn('local PRESET_KEY = "Game1_FireTuner_UserPresets_v1"', source)
        self.assertIn('math.clamp(math.abs(tonumber(fire.heat)', source)

    def test_placed_effect_is_portable_and_install_remains_opt_in(self):
        source = read("system/studio-plugin/modules/StudioPlacedRigBoneEffects.luau")
        self.assertIn('item:IsA("Fire")', source)
        self.assertIn('if item.ClassName ~= "Attachment" then return false end', source)
        self.assertIn('local clone = item:Clone()', source)
        install = read("system/studio-plugin/install-fire-tuner.ps1")
        self.assertIn("$backupRoot", install)
        self.assertIn('Copy-Item -LiteralPath $destination -Destination $backup', install)


if __name__ == "__main__":
    unittest.main()
