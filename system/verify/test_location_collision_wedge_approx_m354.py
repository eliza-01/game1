"""M354 wedge/corner-wedge non-uniform replacement inspection safety contract.

The pure numeric cases verify the transform decision boundary. Real 3D Studio
primitives still require a live Edit-mode smoke test after installing the patch.
"""
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRANSFORM = ROOT / "system/studio-plugin/modules/StudioLocationCollisionTransform.luau"
REPLACE = ROOT / "system/studio-plugin/modules/StudioLocationInstanceReplace.luau"
COLLISION = ROOT / "system/studio-plugin/modules/StudioLocationCollisionParts.luau"
PREVIEW = ROOT / "system/studio-plugin/modules/StudioLocationInstanceCollisionPreview.luau"
BRIDGE = ROOT / "system/control-center/services/studio_location_instance_bridge.py"
UI = ROOT / "system/control-center/static/location-instance-manager.js"
HTML = ROOT / "system/control-center/static/index.html"


def scale(v, r):
    return tuple(v[i] * r[i] for i in range(3))


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def orthogonal(a, b):
    return abs(dot(a, b)) <= math.sqrt(dot(a, a) * dot(b, b)) * .0001


class WedgeApproxM354(unittest.TestCase):
    def test_axis_aligned_wedge_is_exact_with_nonuniform_scale(self):
        # Yaw 90°, canonical right/up/back axes; visual XYZ ratios 2/3/4.
        basis = [(0, 0, -1), (0, 1, 0), (1, 0, 0)]
        axes = [scale(v, (2, 3, 4)) for v in basis]
        self.assertTrue(all(orthogonal(axes[i], axes[j]) for i, j in
                            [(0, 1), (0, 2), (1, 2)]))
        lengths = [math.sqrt(dot(a, a)) for a in axes]
        self.assertEqual(lengths, [4, 3, 2])
        dims = [lengths[i] * [2, 6, 8][i] for i in range(3)]
        self.assertEqual(dims, [8, 18, 16])

    def test_rotated_wedge_produces_shear_and_needs_approval(self):
        theta = math.pi / 4
        axes = [scale((math.cos(theta), 0, math.sin(theta)), (2, 1, 1)),
                scale((0, 1, 0), (2, 1, 1)),
                scale((-math.sin(theta), 0, math.cos(theta)), (2, 1, 1))]
        self.assertFalse(orthogonal(axes[0], axes[2]))
        t = TRANSFORM.read_text(encoding='utf8')
        self.assertIn('local approximate = recipe.shape ~= "Block"', t)
        self.assertIn('if approximate and allowExcessive ~= true then', t)
        self.assertIn('slope/curvature may differ', t)
        self.assertIn('wedge or (cylinder and matchingRadii)', t)
        self.assertIn('CFrame.fromMatrix(centre, scaledRight.Unit, scaledUp.Unit, scaledBack.Unit)', t)

    def test_approx_still_uses_wedge_not_replacement_block(self):
        s = COLLISION.read_text(encoding='utf8')
        self.assertIn('part = Instance.new("WedgePart")', s)
        self.assertIn('part = Instance.new("CornerWedgePart")', s)
        self.assertIn('Transform.Part(anchor, recipe, true)', s)
        self.assertIn('Transform.Part(anchor, recipe)', s)
        self.assertIn('if #transaction.warnings > 0 then transaction.sha else nil', s)

    def test_preview_and_replace_are_identical_and_report_approximation(self):
        repl = REPLACE.read_text(encoding='utf8')
        preview = PREVIEW.read_text(encoding='utf8')
        bridge = BRIDGE.read_text(encoding='utf8')
        ui = UI.read_text(encoding='utf8')
        html = HTML.read_text(encoding='utf8')
        self.assertIn('collisionFingerprint(stage)', repl)
        self.assertIn('part.ClassName', repl)
        self.assertIn('shape=warning.shape,approximate=warning.approximate,reason=warning.reason', repl)
        self.assertIn('APPROX · ', preview)
        self.assertIn('copy.CanCollide = false', preview)
        self.assertIn('copy.CanQuery = false', preview)
        self.assertIn("item.get('approximate')", bridge)
        self.assertIn('row.approximate', ui)
        self.assertIn('Разрешить увеличенные / приближённые коллизии', html)
        self.assertIn('if current.inspectedWarnings > 0 and command.approveShear ~= true then', repl)


if __name__ == '__main__':
    unittest.main()
