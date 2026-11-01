"""M185: preserve the hinge rest frame while restoring the authored mesh centre."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "system/asset-manager/real_estate_part_placement.py"
MODULE = ROOT / "system/studio-plugin/modules/StudioRealEstatePartPlacement.luau"

spec = importlib.util.spec_from_file_location("part_placement_m185", SRC)
placement = importlib.util.module_from_spec(spec)
spec.loader.exec_module(placement)


class ImportedDoorRebaseM185(unittest.TestCase):
    def test_measured_level5_centre_and_hinge_rebase(self):
        house_center = (.04516983, .01792431, 21.64680481)
        door_center = (2.49234812, 7.50634050, 10.13221073)
        door_hinge = (-.40472284, 7.52269840, 9.47613907)
        def points(centre, half):
            return [(centre[0]+x*half[0], centre[1]+y*half[1], centre[2]+z*half[2])
                    for x in (-1,1) for y in (-1,1) for z in (-1,1)]
        authored = placement.placement(points(house_center, (18.978149, 20.310326, 21.646805)),
                                       points(door_center, (2.897071, .618798, 3.964360)))
        self.assertEqual(authored['version'], 2)
        self.assertAlmostEqual(authored['centerInHouse'][0], -2.447178, places=4)
        self.assertAlmostEqual(authored['centerInHouse'][1], -11.514594, places=4)
        self.assertAlmostEqual(authored['centerInHouse'][2], 7.488416, places=4)

        studio_house = (-.04516983, 21.64680481, .017928)
        studio_door = (-2.492348, 10.132211, -4.599523)
        studio_hinge = (.404723, 9.476135, 7.522702)
        expected_door = tuple(studio_house[i] + authored['centerInHouse'][i] for i in range(3))
        delta = tuple(expected_door[i] - studio_door[i] for i in range(3))
        self.assertAlmostEqual(delta[0], 0, places=4)
        self.assertAlmostEqual(delta[1], 0, places=4)
        self.assertAlmostEqual(delta[2], 12.105867, places=3)
        expected_hinge = (-door_hinge[0], door_hinge[2], door_hinge[1])
        for a,b in zip(studio_hinge, expected_hinge):
            self.assertAlmostEqual(a, b, places=4)
        # Root bone rest world position must be invariant under rebase:
        # newMesh + newBoneLocal == oldMesh + oldBoneLocal.
        original_bone_local = tuple(studio_hinge[i] - studio_door[i] for i in range(3))
        recovered_local = tuple(original_bone_local[i] - delta[i] for i in range(3))
        self.assertAlmostEqual(recovered_local[2], 0.01636, places=3)
        for i in range(3):
            self.assertAlmostEqual(expected_door[i] + recovered_local[i], studio_hinge[i], places=4)

    def test_all_root_bone_frames_preserved_while_static_parts_use_rig_pivot(self):
        source = MODULE.read_text('utf-8')
        self.assertIn('raw.version == 1', source)
        self.assertIn('Vector3.new(-center.X, center.Y, -center.Z)', source)
        self.assertIn('child:IsA("Attachment")', source)
        self.assertIn('entry.attachment.CFrame = mesh.CFrame:ToObjectSpace(entry.world)', source)
        self.assertIn('mesh.CFrame = CFrame.new(delta) * oldMesh', source)
        self.assertIn('rig:PivotTo(CFrame.new(delta) * rig:GetPivot())', source)
        self.assertIn('root attachment moved during mesh origin recovery', source)
        self.assertIn('skinned mesh has no root attachments to rebase', source)
        self.assertIn('Game1AuthoredPlacementMode', source)
        self.assertIn('Game1AuthoredPlacementDelta', source)
        self.assertIn('Game1AuthoredPlacementVersion', source)

if __name__ == '__main__':
    unittest.main()
