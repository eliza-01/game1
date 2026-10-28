"""Coverage of vertices is independent from coverage of authored bones."""
import copy
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/asset-manager'))
from bone_weight_survival import plan_publication_weights


class VertexCoverageTests(unittest.TestCase):
    def assert_valid(self, heads, vertices):
        for v in vertices:
            self.assertGreater(len(v['weights']), 0)
            self.assertLessEqual(len(v['weights']), 4)
            self.assertAlmostEqual(sum(v['weights'].values()), 1)
        for bone in heads:
            self.assertTrue(any(v['weights'].get(bone, 0) >= .05 for v in vertices))

    def test_fully_unweighted_mesh_and_multiple_roots(self):
        heads = {'left': (-5, 0, 0), 'right': (5, 0, 0)}
        vertices = [{'position': (x, 0, 0), 'weights': {}} for x in range(-10, 11)]
        report = plan_publication_weights(heads, vertices)
        self.assert_valid(heads, vertices)
        self.assertEqual(report['unweightedVerticesBefore'], 21)
        self.assertEqual(report['unweightedVerticesAfter'], 0)
        self.assertEqual(vertices[0]['weights'], {'left': 1})
        self.assertEqual(vertices[-1]['weights'], {'right': 1})
        self.assertEqual(vertices[10]['weights'], {'left': 1})

    def test_partially_weighted_mesh_preserves_existing_skin(self):
        vertices = [{'position': (0, 0, 0), 'weights': {'a': .7, 'b': .3}},
                    {'position': (3, 0, 0), 'weights': {}},
                    {'position': (4, 0, 0), 'weights': {'unrelated_group': 1}}]
        report = plan_publication_weights({'a': (0,0,0), 'b': (4,0,0)}, vertices)
        self.assertEqual(report['unweightedVerticesBefore'], 2)
        self.assertAlmostEqual(vertices[0]['weights']['a'], .7)
        self.assertAlmostEqual(vertices[0]['weights']['b'], .3)
        self.assertEqual(vertices[1]['weights'], {'b': 1})

    def test_repeated_preparation_is_idempotent(self):
        heads = {'a': (0,0,0), 'b': (10,0,0), 'unused_socket': (100,0,0)}
        vertices = [{'position': (i,0,0), 'weights': {}} for i in range(20)]
        plan_publication_weights(heads, vertices)
        before = copy.deepcopy(vertices)
        report = plan_publication_weights(dict(reversed(list(heads.items()))), vertices)
        self.assertEqual(before, vertices)
        self.assertEqual(report['unweightedVerticesBefore'], 0)
        self.assertEqual(report['patchedBoneCount'], 0)
        self.assert_valid(heads, vertices)

    def test_invalid_weights_do_not_leave_uncovered_vertices(self):
        heads = {'a': (0,0,0), 'b': (2,0,0)}
        vertices = [{'position': (0,0,0), 'weights': {'a': float('nan'), 'b': -1}},
                    {'position': (2,0,0), 'weights': {'a': 1e308, 'b': 1e308}}]
        plan_publication_weights(heads, vertices)
        self.assert_valid(heads, vertices)

    def test_nonfinite_geometry_rejected(self):
        with self.assertRaisesRegex(ValueError, 'finite 3D'):
            plan_publication_weights({'a': (0,0,0)},
                                     [{'position': (float('nan'),0,0), 'weights': {}}])

    def test_shared_validator_rejects_uncovered_vertex_even_if_all_bones_survive(self):
        spec = importlib.util.spec_from_file_location('publication_vertex_test',
                    ROOT / 'system/asset-manager/model_publication.py')
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'bpy': SimpleNamespace()}):
            spec.loader.exec_module(module)
        rig = SimpleNamespace(data=SimpleNamespace(bones=[SimpleNamespace(name='root')]))
        mesh = SimpleNamespace(name='any_mesh', vertex_groups=[SimpleNamespace(index=0,name='root')],
                 data=SimpleNamespace(vertices=[SimpleNamespace(index=0,groups=[SimpleNamespace(group=0,weight=1)]),
                                                SimpleNamespace(index=1,groups=[])]))
        with self.assertRaisesRegex(ValueError, 'vertex 1'):
            module.assert_skin_complete(rig, [mesh])
        mesh.data.vertices[1].groups = [SimpleNamespace(group=0,weight=.2)]
        with self.assertRaisesRegex(ValueError, 'normalized'):
            module.assert_skin_complete(rig, [mesh])
        mesh.data.vertices[1].groups[0].weight = 1
        module.assert_skin_complete(rig, [mesh])


if __name__ == '__main__':
    unittest.main()
