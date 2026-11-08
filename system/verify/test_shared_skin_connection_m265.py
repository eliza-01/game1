"""M265 shared skeletal assembly contract (Studio behaviour still needs Play test).

The engine's Bone resolver and Weld physics are not emulated by this test.
We verify the code ownership, validation order and bounds, then require a
real Studio smoke test to confirm skinning and rigid COL placement.
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def source(path):
    return (ROOT / path).read_text(encoding='utf-8')


class SharedSkinConnectionM265(unittest.TestCase):
    def test_character_and_plugin_reference_one_source_file(self):
        manifest = json.loads(source('system/studio-plugin/plugin.project.json'))
        self.assertEqual(
            manifest['tree']['modules']['StudioSkinnedMeshConnection']['$path'],
            '../../src/shared/rig/SkinnedMeshConnection.luau')
        character = source('src/server/character/CharacterAssemblyBuilder.luau')
        self.assertIn(':WaitForChild("rig"):WaitForChild("SkinnedMeshConnection")', character)
        self.assertIn('SkinConnection.Connect(imported, carrier, mesh, "CharacterSkinWeld")', character)
        self.assertEqual(character.count('Instance.new("Weld")'), 0)
        loader = source('system/studio-plugin/modules/DecoAssetLoader.luau')
        self.assertIn('require(script.Parent.StudioSkinnedMeshConnection)', loader)
        self.assertIn('SkinConnection.Connect(model, carrier, part, weldName)', loader)

    def test_shared_mechanism_links_only_missing_skin_assembly_path(self):
        conn = source('src/shared/rig/SkinnedMeshConnection.luau')
        for marker in ('instance:IsA("JointInstance")',
                       'instance:IsA("WeldConstraint")',
                       'instance.Part0, instance.Part1',
                       'seen[other] = true',
                       'if part == target then return true end',
                       'if connected(model, carrier, mesh) then return false end',
                       'weld.Part0 = carrier', 'weld.Part1 = mesh',
                       'weld.C0 = carrier.CFrame:ToObjectSpace(mesh.CFrame)',
                       'weld.C1 = CFrame.identity',
                       'weld.Parent = mesh'):
            self.assertIn(marker, conn)
        self.assertLess(conn.index('if connected(model, carrier, mesh) then return false end'),
                        conn.index('Instance.new("Weld")'))
        self.assertNotIn('Bone:Destroy()', conn)
        self.assertNotIn('Anchored =', conn)
        self.assertNotIn('PivotTo(', conn)
        self.assertNotIn('MeshId =', conn)
        self.assertIn('FindFirstAncestorOfClass("Model") == model', conn)
        self.assertIn('invalid or external joint', conn)

    def test_location_connected_only_for_published_skinned_detached_clone(self):
        loader = source('system/studio-plugin/modules/DecoAssetLoader.luau')
        self.assertLess(loader.index('sanitize(model)'),
                        loader.index('PublishedRigNormalize.Apply(model, row.rigManifest)'))
        self.assertLess(loader.index('PublishedRigNormalize.Apply(model, row.rigManifest)'),
                        loader.index('Carrier.Validate(model, row.rigManifest, row.legacyStaticPublication)'))
        self.assertLess(loader.index('Carrier.Validate(model, row.rigManifest, row.legacyStaticPublication)'),
                        loader.index('SkinConnection.Connect(model, carrier, part, weldName)'))
        self.assertIn('if carrier then', loader)
        self.assertIn('part ~= carrier', loader)
        self.assertIn('MeshPhysics.IsCollider(part.Name)', loader)
        self.assertIn('"LocationRigWeld"', loader)
        self.assertIn('"LocationSkinWeld"', loader)
        self.assertLess(loader.index('SkinConnection.Connect(model, carrier, part, weldName)'),
                        loader.index('model.PrimaryPart = carrier'))
        self.assertIn('descendant.Anchored = true', loader)
        place = source('system/studio-plugin/modules/DecoAssetPreparation.luau')
        self.assertIn('descendant.Anchored = false', place)
        self.assertIn('RigSwap.Commit(', source('system/studio-plugin/modules/StudioPlaceRegistrySync.luau'))
        self.assertIn('RigSwap.Commit(', source('system/studio-plugin/modules/DecoPlacedAssetSync.luau'))


if __name__ == '__main__':
    unittest.main()
