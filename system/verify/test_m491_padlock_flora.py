"""M491 source contracts. Actual Bone/streaming behavior: Studio smoke scripts."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def src(path):
    return (ROOT / path).read_text(encoding='utf8')


class PadlockFloraM491(unittest.TestCase):
    def test_mount_copies_bone_head_and_full_orientation(self):
        mount = src('src/shared/rig/PivotSocketMount.luau')
        self.assertIn('return (socket :: Bone).TransformedWorldCFrame\n', mount)
        self.assertNotIn('OBJECT_TO_BONE', mount)
        self.assertIn('local delta = targetFrame * origin:GetPivot():Inverse()', mount)
        self.assertIn('model:PivotTo(delta * model:GetPivot())', mount)
        self.assertNotIn('SpawnOrientation.Upright', mount)
        self.assertNotIn('SocketFacing.FullFrame', mount)
        self.assertIn('pcall(Mount.CloneOnPivot, SLUG, socket)', src('src/server/world/HousePadlockVisuals.luau'))

    def test_streamed_geometry_and_late_identity_refresh(self):
        index = src('src/client/world/FloraContactIndex.luau')
        self.assertIn('model.AttributeChanged:Connect', index)
        self.assertIn('watch(obj); schedule(obj)', index)
        self.assertEqual(index.count('elseif obj:IsA("MeshPart") then geometryChanged(obj) end'), 2)
        self.assertIn('task.defer(function()', index)
        self.assertIn('connection:Disconnect(); watched[model] = nil', index)
        self.assertIn('for _, record in ipairs(records) do erase(record) end', index)
        self.assertIn('if #records > 0 then entries[model] = records end', index)
        self.assertIn('insert(part.CFrame, part.Size, model)', index)
        self.assertIn('not Physics.IsLocationCarrier(part)', index)
        self.assertIn('if not slug or compiledTargets[slug] then return end', index)
        self.assertIn('(Registry.aliases or {})[slug] or slug', index)
        self.assertEqual(index.count('Workspace:GetDescendants()'), 1)

    def test_low_bushes_and_first_contact_diagnostics(self):
        controller = src('src/client/world/FloraLeafBurstController.luau')
        self.assertIn('if root ~= lastRoot then', controller)
        self.assertIn('Index.Find(position, padding)', controller)
        self.assertIn('Index.Find(midpoint, padding)', controller)
        self.assertIn('if not Index.Start() then', controller)
        self.assertIn('if not reportedContact then', controller)
        self.assertIn('base.DoubleSided = true', src('src/client/world/FloraLeafPool.luau'))
        self.assertIn('lastContact = now', controller)


if __name__ == '__main__':
    unittest.main()
