"""M288: no COL required for skinned Location FBX importer RootPart normalization."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULES = ROOT / 'system/studio-plugin/modules'


class LocationOptionalCollisionTests(unittest.TestCase):
    def test_imported_root_can_be_normalized_without_authored_col(self):
        source = (MODULES / 'StudioLocationPublishedRigNormalize.luau').read_text('utf-8')
        self.assertNotIn('RootPart has no authored collider replacement', source)
        self.assertNotIn('if not hasCollider then', source)
        self.assertIn('for name, role in pairs(expected) do', source)
        self.assertIn('if role == "collider" then', source)
        self.assertIn('published Location is missing declared collider:', source)
        self.assertIn('root:Destroy()', source)
        self.assertNotIn('Instance.new(', source)

    def test_root_removal_is_only_on_detached_load_and_poses_are_unchanged(self):
        source = (MODULES / 'StudioLocationPublishedRigNormalize.luau').read_text('utf-8')
        loader = (MODULES / 'DecoAssetLoader.luau').read_text('utf-8')
        for guard in (
            'model.Parent ~= nil',
            'manifest.rigKind ~= "skinned"',
            'root.Transparency < 0.99',
            'importer RootPart has no authored rig_carrier target',
            'importer RootPart Motor6D has an unsafe endpoint',
            'bone.WorldCFrame',
            'bone.Transform',
            'importer normalization changed published Bone pose',
            'importer normalization changed published Model pivot',
        ):
            self.assertIn(guard, source)
        self.assertLess(loader.index('PublishedRigNormalize.Apply('),
                        loader.index('Carrier.Validate('))
        self.assertLess(loader.index('Carrier.Validate('),
                        loader.index('MeshPhysics.ApplyLocationModel('))

    def test_physics_remains_in_shared_core(self):
        source = (ROOT / 'src/shared/world/MeshPhysicsCore.luau').read_text('utf-8')
        self.assertIn('if hasCollider then not collider else not (collider or namedGlass)', source)
        self.assertIn('Legacy Location without COL: do not override', source)


if __name__ == '__main__':
    unittest.main()
