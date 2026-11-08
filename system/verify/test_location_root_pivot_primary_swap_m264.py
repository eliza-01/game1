"""M264 regression: relocating a PrimaryPart pivot must not move placed geometry.

The numerical test exercises rigid-frame composition independent of Roblox.
The source contracts still require an Edit-mode Studio smoke test for engine
PivotOffset/PrimaryPart semantics, skinned Bones and loaded Motor6D joints.
"""
import math
from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]
MODULES = ROOT / 'system/studio-plugin/modules'


def compose(a, b):
    x, y, r = a
    u, v, s = b
    return (x + math.cos(r)*u - math.sin(r)*v,
            y + math.sin(r)*u + math.cos(r)*v, r+s)


def inverse(a):
    x, y, r = a
    return (-math.cos(r)*x - math.sin(r)*y,
            math.sin(r)*x - math.cos(r)*y, -r)


def close(a, b, tolerance=1e-6):
    return all(abs(x-y)<tolerance for x,y in zip(a,b))


class PlacedRootPrimarySwapM264(TestCase):
    def source(self, name):
        return (MODULES/name).read_text(encoding='utf-8')

    def test_rebase_corrects_translation_and_90_degree_primary_rotation(self):
        placed_root = (22.0, -7.0, 0.2)
        incoming_primary_geometry = (28.332645, -7.0, 0.2+math.pi/2)
        authored_offset = (0,0,0)
        self.assertFalse(close(compose(incoming_primary_geometry, authored_offset), placed_root))
        # Equivalent to newPrimary.CFrame:ToObjectSpace(plan.pivot).
        rebased_offset = compose(inverse(incoming_primary_geometry), placed_root)
        self.assertTrue(close(compose(incoming_primary_geometry, rebased_offset), placed_root))
        # Rebasing Part.PivotOffset is NOT Model:PivotTo: the mesh frame stays fixed.
        self.assertTrue(close(incoming_primary_geometry, (28.332645,-7.0,0.2+math.pi/2)))

    def test_future_provenance_ignores_rebased_pivot_metadata(self):
        placement = (9.0, 3.0, 0.5)
        old_template_parts = [(2.0,4.0,0.3),(-3.0,1.0,-0.7)]
        placed = [compose(placement, frame) for frame in old_template_parts]
        incoming_pivot_metadata = compose(inverse(placed[0]), (100,20,1))
        self.assertFalse(close(compose(placed[0],incoming_pivot_metadata),placed[0]))
        for published, actual in zip(old_template_parts,placed):
            self.assertTrue(close(compose(actual,inverse(published)),placement))
        # A GetPivot()-based candidate would incorrectly use the compensated offset.
        self.assertFalse(close(compose(compose(placed[0],incoming_pivot_metadata),
                                       inverse(old_template_parts[0])), placement))

    def test_shared_swap_preserves_placement_and_rollback_contract(self):
        swap=self.source('StudioManagedRigSwap.luau')
        locate='plan.newPrimary.PivotOffset = plan.newPrimary.CFrame:ToObjectSpace(plan.pivot)'
        self.assertEqual(swap.count(locate),1)
        self.assertLess(swap.index('for _, child in ipairs(plan.incoming) do child.Parent = plan.root end'),
                        swap.index(locate))
        self.assertLess(swap.index(locate),swap.index('plan.root.PrimaryPart = plan.newPrimary'))
        self.assertIn('if not sameFrame(actualPivot, plan.pivot)',swap)
        self.assertIn('or math.abs(actualScale - plan.scale) > 0.000001',swap)
        self.assertIn('or plan.root.Parent ~= plan.parent',swap)
        self.assertIn('plan.root.PrimaryPart = plan.primary',swap)
        self.assertIn('for _, entry in ipairs(plan.old) do entry.object:Destroy() end',swap)
        self.assertNotIn('plan.root:PivotTo(plan.pivot)',swap)
        self.assertNotIn('plan.root:ScaleTo(',swap)

    def test_future_mesh_provenance_uses_geometry_frame(self):
        history=self.source('StudioPublishedMeshHistory.luau')
        self.assertIn('local candidate = placedParts[1].CFrame * oldParts[1].CFrame:Inverse()',history)
        self.assertNotIn('placedParts[1]:GetPivot() * oldParts[1]:GetPivot():Inverse()',history)
        for adapter in ('DecoPlacedAssetSync.luau','StudioPlaceRegistrySync.luau',
                        'StudioRealEstatePlacedVisualSync.luau'):
            self.assertIn('RigSwap.Prepare(',self.source(adapter))
            self.assertIn('RigSwap.Commit(',self.source(adapter))
