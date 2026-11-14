"""M350 non-uniform Location collision: numeric box containment + source contracts.

No Roblox Studio engine calls here: the sample coordinates/ratios come from the
2026-11-14 Place snapshot and collision revision 3, but no Place data is changed.
"""
import itertools
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Stone fence published anchor and collision Block r3; local coordinates with
# only their relative rotation matter for this particular envelope regression.
ANCHOR_SIZE = (3.407264232635498, 5.484735488891602, 17.768489837646484)
PART_SIZE = (2.753999948501587, 17.320999145507812, 5.250999927520752)
ROTATION = (
    (0.999903440, 0.0138883789, -0.00000522354),
    (-0.00000504222, -0.00001309085, -1.0),
    (-0.0138883508, 0.999903560, -0.00001301956),
)


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def projected_enclosure(base_size, ratios, rotation):
    columns = [tuple(rotation[row][i] for row in range(3)) for i in range(3)]
    transformed = [tuple(a*ratio for a, ratio in zip(column, ratios)) for column in columns]
    sizes = [sum(abs(dot(columns[i], transformed[j]))*base_size[j]
                 for j in range(3)) for i in range(3)]
    return sizes, columns, transformed


class NonuniformCollisionM350(unittest.TestCase):
    def test_exact_affine_centre_and_tight_enclosure_for_legacy_sizes(self):
        placed_sizes = (
            (3.407264232635498, 7.832838535308838, 17.768489837646484),
            (3.407264232635498, 7.832838535308838, 7.385961532592773),
            (4.687413215637207, 7.360165119171143, 12.441858291625977),
        )
        for placed in placed_sizes:
            ratios = [x/y for x, y in zip(placed, ANCHOR_SIZE)]
            enclosing, columns, transformed = projected_enclosure(PART_SIZE, ratios, ROTATION)
            # Every original box corner after *per-axis* scaling must lie inside
            # the resulting rigid oriented Block; this checks all 8 vertices.
            for signs in itertools.product((-1, 1), repeat=3):
                affine_corner = [sum(signs[j]*PART_SIZE[j]*transformed[j][k]/2
                                    for j in range(3)) for k in range(3)]
                for axis in range(3):
                    self.assertLessEqual(abs(dot(columns[axis], affine_corner)),
                                         enclosing[axis]/2 + 1e-4)
            # The real historical captures require only a slight inflation.
            lower = [math.sqrt(dot(v,v))*size for v, size in zip(transformed, PART_SIZE)]
            self.assertLessEqual(max(s-l for s,l in zip(enclosing, lower)), .20)

    def test_uniform_case_keeps_legacy_exact_size(self):
        ratios = (2.0, 2.0, 2.0)
        enclosing, _, _ = projected_enclosure(PART_SIZE, ratios, ROTATION)
        for result, expected in zip(enclosing, PART_SIZE):
            self.assertAlmostEqual(result, expected*2, delta=0.0001)

    def test_single_shared_transform_for_scan_and_sync(self):
        collision = (ROOT/'system/studio-plugin/modules/StudioLocationCollisionParts.luau').read_text()
        transform = (ROOT/'system/studio-plugin/modules/StudioLocationCollisionTransform.luau').read_text()
        bundle = (ROOT/'system/studio-plugin/plugin.project.json').read_text()
        self.assertIn('pcall(Transform.Resolve, root, blueprint)', collision)
        self.assertIn('Transform.Resolve(geometry, blueprint)', collision)
        self.assertIn('Transform.Part, anchor, recipe', collision)
        self.assertIn('Transform.Part(anchor, recipe)', collision)
        self.assertIn('StudioLocationCollisionTransform.luau', bundle)
        self.assertIn('anchor.anchorFrame:ToObjectSpace(source)', transform)
        self.assertIn('matched.Size.X / original.X', transform)
        self.assertIn('scaleVector(relative.Position, ratios)', transform)
        self.assertIn('math.abs(right:Dot(scaledRight))', transform)
        self.assertIn('Non-uniform visual MeshPart Size requires Block collision Parts', transform)
        self.assertNotIn('PivotTo(', transform)
        self.assertNotIn('PivotOffset =', transform)


if __name__ == '__main__':
    unittest.main()
