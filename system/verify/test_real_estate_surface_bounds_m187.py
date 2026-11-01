"""Placement must describe FBX faces that survive Roblox's mesh import."""
import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('surface_bounds_m187', ROOT/'system/asset-manager/real_estate_part_placement.py')
placement = importlib.util.module_from_spec(spec)
spec.loader.exec_module(placement)


class Identity:
    def __matmul__(self, other):
        return other

    def __getitem__(self, row):
        return tuple(float(row == col) for col in range(3))

    def inverted_safe(self):
        return self

    def to_3x3(self):
        return self

    def normalized(self):
        return self


def mesh(name, center, size, extra=()):
    points = [tuple(center[i] + sign[i]*size[i]/2 for i in range(3))
              for sign in [(x,y,z) for x in (-1,1) for y in (-1,1) for z in (-1,1)]]
    return SimpleNamespace(name=name, matrix_world=Identity(),
        data=SimpleNamespace(vertices=[SimpleNamespace(co=p) for p in points + list(extra)],
            polygons=[SimpleNamespace(vertices=tuple(range(8)))]))


class SurfaceBounds(unittest.TestCase):
    def test_loose_vertices_and_wire_endpoints_do_not_change_size_or_centre(self):
        house = mesh('house', (0,0,10), (20,30,20), [(999,999,999)])
        collider = mesh('col_mesh', (1,2,8), (18,28,16), [(-100,-200,-300),(400,500,600)])
        result = placement.inspect_placements(house, [house, collider])
        self.assertEqual(result['house']['size'], [20,20,30])
        self.assertEqual(result['house']['centerInHouse'], [0,0,0])
        self.assertEqual(result['col_mesh']['size'], [18,16,28])
        self.assertEqual(result['col_mesh']['centerInHouse'], [-1,-2,2])

    def test_vertex_only_objects_fail_instead_of_fabricating_surface_bounds(self):
        house = mesh('house', (0,0,0), (10,10,10))
        invalid = mesh('col_mesh', (0,0,0), (10,10,10))
        invalid.data.polygons = []
        with self.assertRaisesRegex(ValueError, 'no surface faces'):
            placement.inspect_placements(house, [invalid])

    def test_measured_level5_surface_matches_published_roblox_geometry(self):
        house = mesh('house', (.0451688766,.0179262161,21.6468047965),
                     (37.9563007355,40.6206493378,43.2936096453))
        collider = mesh('col_mesh', (.0505924225,.5213041306,21.5035576560),
                        (37.8274574280,41.4667568207,43.2060347125), [(49,0,-2)])
        result = placement.inspect_placements(house, [collider])['col_mesh']
        self.assertAlmostEqual(result['size'][0], 37.827457, places=5)
        self.assertAlmostEqual(result['size'][1], 43.206039, places=5)
        self.assertAlmostEqual(result['size'][2], 41.466755, places=5)
        self.assertAlmostEqual(result['centerInHouse'][0], -.005424, places=5)
        self.assertAlmostEqual(result['centerInHouse'][1], -.143247, places=5)


if __name__ == '__main__':
    unittest.main()
