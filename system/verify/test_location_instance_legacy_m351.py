"""M351: legacy geometry provenance / source Size / protocol-v4 invariants.

Numerical checks use the saved source geometry semantics and selected target
pivot. Luau/Studio physics, Undo and actual published asset loading still need
one-place manual acceptance on a verified historical fence.
"""
import math
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PARTS = ROOT / 'system/studio-plugin/modules'
LUA = (PARTS / 'StudioLocationInstanceLegacyGeometry.luau').read_text(encoding='utf8')
REPLACE = (PARTS / 'StudioLocationInstanceReplace.luau').read_text(encoding='utf8')
JS = (ROOT / 'system/control-center/static/location-instance-manager.js').read_text(encoding='utf8')
BRIDGE = (ROOT / 'system/control-center/services/studio_location_instance_bridge.py').read_text(encoding='utf8')


def transpose(m): return tuple(zip(*m))
def matmul(a,b): return tuple(tuple(sum(a[i][k]*b[k][j] for k in range(3)) for j in range(3)) for i in range(3))
def mmv(m,v): return tuple(sum(m[i][k]*v[k] for k in range(3)) for i in range(3))
def mul(a,b):
    p,r=a; q,s=b
    t=mmv(r,q)
    return (tuple(p[i]+t[i] for i in range(3)), matmul(r,s))
def inverse(a):
    p,r=a; t=transpose(r); q=mmv(t,p)
    return (tuple(-v for v in q),t)
def frame(pos,rotation): return (pos,rotation)
E=((1,0,0),(0,1,0),(0,0,1))
RY=((0,0,1),(0,1,0),(-1,0,0))
RX=((1,0,0),(0,0,-1),(0,1,0))


class LegacyGeometryM351(unittest.TestCase):
    def test_historic_pivot_recovery_from_mesh_cframe_ignores_rebased_pivot_offset(self):
        # Published Model pivot != published MeshPart CFrame. A historical
        # Sync may change only MeshPart.PivotOffset, not mesh's world CFrame.
        published_model = frame((0,-2.72,0),E)
        published_mesh = frame((0,0,0),RX)
        placed_mesh = frame((446,-47,-265),RY)
        broken_placed_model = frame((446,-47,-265),RY)
        recovered = mul(mul(placed_mesh,inverse(published_mesh)),published_model)
        transform = mul(placed_mesh,inverse(published_mesh))
        self.assertEqual(recovered,mul(transform,published_model))
        self.assertNotEqual(recovered,broken_placed_model)
        # Selecting NEW Model or NEW MeshPart must land that selected anchor
        # at the recovered source frame, not the bad placed root pivot.
        target_model=frame((10,2,-5),E)
        target_mesh=frame((11,0,-5),RX)
        for anchor in (target_model,target_mesh):
            next_model=mul(mul(recovered,inverse(anchor)),target_model)
            next_anchor=mul(mul(next_model,inverse(target_model)),anchor)
            self.assertEqual(next_anchor,recovered)

    def test_legacy_size_ratios_on_saved_stone_fence_differ_per_axis(self):
        authored=(3.407264,5.484735,17.76849)
        old=(3.407264,7.833,7.386)
        ratios=tuple(a/b for a,b in zip(old,authored))
        self.assertAlmostEqual(ratios[0],1,places=5)
        self.assertAlmostEqual(ratios[1],1.428,places=2)
        self.assertAlmostEqual(ratios[2],0.416,places=2)
        target_authored=(2,4,20)
        expected=tuple(a*r for a,r in zip(target_authored,ratios))
        self.assertAlmostEqual(expected[0],2,places=5)
        self.assertAlmostEqual(expected[1],5.713,places=2)
        self.assertAlmostEqual(expected[2],8.313,places=2)
        # Compare to old M347: only old Model.GetScale=1, loses these edits.
        self.assertNotEqual(expected,target_authored)

    def test_basis_permutation_can_map_dimension_axes_without_guessing(self):
        src=E
        tgt=RX
        # Target X aligns source X; target Y aligns source Z; target Z aligns source Y.
        relative=matmul(transpose(src),tgt)
        ratios=(1,1.43,.42)
        mapped=[]
        for column in range(3):
            axis=tuple(relative[row][column] for row in range(3))
            matches=[abs(x) for x in axis]
            self.assertGreaterEqual(max(matches),.999)
            mapped.append(ratios[matches.index(max(matches))])
        self.assertEqual(mapped,[1,.42,1.43])
        # An arbitrary diagonal is shear under non-uniform stretch: no silent resize.
        h=math.sqrt(.5)
        diagonal=((h,-h,0),(h,h,0),(0,0,1))
        self.assertLess(max(abs(diagonal[i][0]) for i in range(3)),.999)

    def test_preview_checks_target_compatibility_and_never_writes_source(self):
        self.assertIn('function Legacy.Inspect(placed: Model,published: Model)',LUA)
        self.assertIn('old.CFrame * reference.CFrame:Inverse() * published:GetPivot()',LUA)
        self.assertIn('ratios(old.Size,reference.Size*scale)',LUA)
        self.assertIn('if pivotRebased then recovered else placed:GetPivot()',LUA)
        self.assertIn('if not dryRun then targetPart.Size=newSize end',LUA)
        self.assertIn('Legacy.ResizeTarget(template,state.geometry,true)',REPLACE)
        self.assertIn('Legacy.ResizeTarget(clone,old.geometry)',REPLACE)
        self.assertIn('referenceById[assetId]=reference',REPLACE)
        self.assertNotIn('source.PivotOffset =',LUA)
        self.assertNotIn('placed:PivotTo(',LUA)
        self.assertNotIn('placed:ScaleTo(',LUA)
        self.assertIn('pair.before.root.Parent = nil',REPLACE)
        self.assertIn('TryBeginRecording',REPLACE)

    def test_v4_bridge_binds_all_parts_of_replace_and_prevents_stale_plugin(self):
        for file in (PARTS/'StudioLocationInstanceReplace.luau',
                     ROOT/'system/studio-plugin/Game1Bridge.server.luau',
                     ROOT/'system/studio-plugin/install.ps1',
                     ROOT/'system/control-center/services/studio_location_instance_bridge.py'):
            self.assertIn('location-instance-replace-v4',file.read_text(encoding='utf8'))
        self.assertIn('schemaVersion ~= 4',REPLACE)
        self.assertIn('schemaVersion=4',BRIDGE)
        self.assertIn('normalizedPivots',BRIDGE)
        self.assertIn('preservedManualSizes',JS)
        project=(ROOT/'system/studio-plugin/plugin.project.json').read_text(encoding='utf8')
        self.assertIn('StudioLocationInstanceLegacyGeometry',project)
        self.assertIn('location-instance-manager.js?v=351',
                      (ROOT/'system/control-center/static/index.html').read_text(encoding='utf8'))


if __name__ == '__main__': unittest.main()
