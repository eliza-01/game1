"""M417: static house centre is not the imported part pivot."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class StaticHouseSharedPivotM417(unittest.TestCase):
    def test_static_alignment_never_moves_mesh_or_uses_aabb_centre_as_transform(self):
        text = (ROOT / 'system/studio-plugin/modules/StudioRealEstatePartPlacement.luau').read_text()
        method = text.split('function Placement.AlignOrigin(', 1)[1].split('function Placement.Align(', 1)[0]
        self.assertIn('triple(authored.centerInPivot', method)
        self.assertIn('local originalFrame = mesh.CFrame', method)
        self.assertIn('mesh.PivotOffset = originalFrame:ToObjectSpace(housePivot)', method)
        self.assertIn('rig.PrimaryPart = mesh', method)
        self.assertIn('Placement.SamePivot(rig:GetPivot(), housePivot)', method)
        self.assertIn('Placement.SamePivot(mesh.CFrame, originalFrame)', method)
        self.assertNotIn('mesh.Position', method)
        self.assertNotIn('targetPosition', method)
        self.assertNotIn('mesh.CFrame =', method)
        self.assertNotIn('rig:PivotTo(', method)
        self.assertNotIn('mesh.Size[axis] -', method)

    def test_static_provenance_and_structure_checks_remain(self):
        text = (ROOT / 'system/studio-plugin/modules/StudioRealEstatePartPlacement.luau').read_text()
        method = text.split('function Placement.AlignOrigin(', 1)[1].split('function Placement.Align(', 1)[0]
        self.assertIn('authored.version ~= 3', method)
        self.assertIn('source MeshPart is outside the published Model', method)
        self.assertIn('static source unexpectedly contains Bone', method)
        self.assertIn('standalone static Model must contain exactly one BasePart', method)
        self.assertIn('imported MeshPart has invalid dimensions', method)

    def test_root_stage_still_uses_shared_carrier_for_all_parts(self):
        text = (ROOT / 'system/studio-plugin/modules/StudioRealEstateModel.luau').read_text()
        self.assertIn('PartPlacement.AlignOrigin(rig, mesh, authoredOrigin,', text)
        self.assertIn('static.PrimaryPart = rootCarrier', text)
        self.assertIn('wrapper.PrimaryPart = rootCarrier', text)

if __name__ == '__main__':
    unittest.main()
