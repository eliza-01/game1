"""M263: importer Motor6D is allowed only as bounded v2 publication structure."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class LocationImporterMotorAssemblyTests(unittest.TestCase):
    def test_studio_policy_keeps_rootpart_ban_and_validates_internal_motors(self):
        source = (ROOT / 'system/studio-plugin/modules/StudioLocationRigCarrier.luau').read_text('utf-8')
        self.assertIn('published Location asset contains RootPart; republish FBX', source)
        self.assertIn('local function validateImporterMotors', source)
        self.assertIn('part0:IsDescendantOf(model)', source)
        self.assertIn('part1:IsDescendantOf(model)', source)
        self.assertIn('expected[part0.Name] == nil', source)
        self.assertIn('expected[part1.Name] == nil', source)
        self.assertIn('published Location asset contains unsafe importer Motor6D', source)
        self.assertIn('published Location asset contains duplicate importer Motor6D pair', source)
        self.assertIn('published Location asset contains cyclic importer Motor6D assembly', source)
        self.assertNotIn('published Location asset contains importer Motor6D"', source)

    def test_static_publication_still_rejects_motor6d(self):
        source = (ROOT / 'system/studio-plugin/modules/StudioLocationRigCarrier.luau').read_text('utf-8')
        self.assertIn('static Location publication unexpectedly contains Motor6D', source)
        self.assertLess(source.index('validateImporterMotors(model, manifest, expected)'),
                        source.index('for _, child in ipairs(model:GetDescendants()) do',
                                     source.index('validateImporterMotors(model, manifest, expected)')))

    def test_loader_preserves_published_joint_instead_of_rebuilding_it(self):
        loader = (ROOT / 'system/studio-plugin/modules/DecoAssetLoader.luau').read_text('utf-8')
        self.assertNotIn('descendant:IsA("Motor6D") then\n            descendant:Destroy()', loader)
        self.assertIn('Carrier.Validate(model, row.rigManifest, row.legacyStaticPublication)', loader)

    def test_importer_root_normalization_is_fresh_clone_only_and_transform_guarded(self):
        source = (ROOT / 'system/studio-plugin/modules/StudioLocationPublishedRigNormalize.luau').read_text('utf-8')
        for marker in ('model.Parent ~= nil', 'root.Transparency < 0.99',
                       'published Location is missing declared collider:',
                       'bone.WorldCFrame', 'bone.Transform',
                       'part.CFrame ~= state.frame', 'part.Size ~= state.size',
                       'model.WorldPivot = authoredPivot',
                       'importer normalization changed published Model pivot'):
            self.assertIn(marker, source)
        self.assertNotIn('Instance.new(', source)
        self.assertNotIn('root.CanCollide or root.CanTouch or root.CanQuery', source)


if __name__ == '__main__':
    unittest.main()
