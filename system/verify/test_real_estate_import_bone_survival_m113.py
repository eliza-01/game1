"""M113: redundant Estate skin anchors and explicit single-rig Roblox re-publication."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/asset-manager'))
sys.path.insert(0, str(ROOT / 'system/control-center'))
from bone_weight_survival import plan_publication_weights
from real_estate.jobs import RealEstatePublicationJobs
from real_estate.store import RealEstateStore
from test_real_estate_m107 import skeleton


class BoneImportCoverage(unittest.TestCase):
    def test_estate_unweighted_helper_bones_receive_three_strong_independent_anchors(self):
        heads = {name: (i * 5.0, 0, 0) for i, name in enumerate(
            ('chimney_bone', 'elevator_bone', 'floor1_spawn', 'floor2_spawn'))}
        vertices = [{'position': (i / 2, 0, 0), 'index': i,
                     'weights': {'chimney_bone': 1.0}} for i in range(60)]
        report = plan_publication_weights(
            heads, vertices, min_covered_vertices=3,
            minimum_weight=.20, anchor_weight=.30,
        )
        self.assertEqual(report['minimumVerticesPerBone'], 3)
        self.assertEqual(report['minimumInfluence'], .20)
        self.assertEqual(report['survivingBoneCount'], 4)
        for bone in heads:
            indices = [v['index'] for v in vertices if v['weights'].get(bone, 0) >= .20]
            self.assertGreaterEqual(len(indices), 3, bone)
        for v in vertices:
            self.assertLessEqual(len(v['weights']), 4)
            self.assertAlmostEqual(sum(v['weights'].values()), 1.0, places=8)

    def test_existing_sufficient_weighting_is_left_unchanged(self):
        verts = [{'position': (i, 0, 0), 'weights': {'door_bone': 1.0}}
                 for i in range(5)]
        original = [dict(v['weights']) for v in verts]
        report = plan_publication_weights(
            {'door_bone': (0, 0, 0)}, verts,
            min_covered_vertices=3, minimum_weight=.2, anchor_weight=.3)
        self.assertEqual(report['patchedBoneCount'], 0)
        self.assertEqual([v['weights'] for v in verts], original)

    def test_never_silently_reduces_other_completed_bone_coverage(self):
        heads = {f'b{i}': (0, 0, 0) for i in range(5)}
        verts = [{'position': (0, 0, 0), 'weights': {'b0': 1.0}}
                 for _ in range(3)]
        with self.assertRaisesRegex(ValueError, 'no safe'):
            plan_publication_weights(heads, verts, min_covered_vertices=3,
                                     minimum_weight=.2, anchor_weight=.3)

    def test_blender_export_uses_only_estate_coverage_policy(self):
        script = (ROOT / 'system/asset-manager/prepare_real_estate_publication_fbx.py').read_text()
        self.assertIn('min_covered_vertices=3', script)
        self.assertIn('minimum_weight=0.20, anchor_weight=0.30', script)
        self.assertIn('assert_rig_survived', (ROOT / 'system/control-center/real_estate/fbx.py').read_text())
        studio = (ROOT / 'system/studio-plugin/modules/StudioRealEstateModel.luau').read_text()
        self.assertIn('rigWarnings = rigWarnings', studio)
        self.assertIn('DOOR_HINGE = "door_01_hinge_socket"', studio)
        self.assertIn('Model Asset', studio)


class ForceSingleRigPublication(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='estate-m113-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        src = self.root / 'incoming'
        src.mkdir()
        self.fbx = src / 'house_level1_01.fbx'
        self.fbx.write_bytes(b'original fbx')
        self.house = src / 'house.png'
        self.door = src / 'door.png'
        self.house.write_bytes(b'house image')
        self.door.write_bytes(b'door image')
        self.store = RealEstateStore(self.root)
        with patch('real_estate.store.inspect', return_value=skeleton()):
            self.store.register({'sourcePath': str(self.fbx), 'houseType': 'house',
                                 'level': 1, 'variant': '01',
                                 'textures': {'house': str(self.house), 'door': str(self.door)}})
        self.ids = iter(range(50001, 50010))
        self.uploads = []
        self.pending_failure = False

    def publish(self, scope):
        def prepare(root, source, target, expected, textures):
            target.mkdir(exist_ok=True)
            for part in ('house', 'door'):
                (target / (part + '.fbx')).write_bytes(part.encode())
        def upload_model(path, **kwargs):
            self.uploads.append('model:' + path.stem)
            return 'operation/' + path.stem + '/' + str(len(self.uploads))
        def upload_image(path, **kwargs):
            self.uploads.append('image:' + kwargs['display_name'].split()[-1])
            return 'operation/image/' + str(len(self.uploads))
        def wait(operation, **kwargs):
            if self.pending_failure:
                self.pending_failure = False
                raise TimeoutError('offline')
            return SimpleNamespace(asset_id=next(self.ids), moderation_state='Approved')
        with patch('real_estate.store.prepare_publication', side_effect=prepare), \
             patch('real_estate.store.prepare_texture', side_effect=lambda root, part, source, dest: source), \
             patch('real_estate.store.create_model_asset', side_effect=upload_model), \
             patch('real_estate.store.create_image_asset', side_effect=upload_image), \
             patch('real_estate.store.wait_for_operation', side_effect=wait):
            return self.store.publish('house_level1_01', {
                'apiKey': 'test', 'creatorType': 'user', 'creatorId': '1'}, scope=scope)

    def test_only_republishes_house_model_preserving_other_ids_and_source(self):
        first = self.publish('all')
        self.assertEqual(first['status'], 'PUBLISHED')
        original_bytes = self.fbx.read_bytes()
        old_house = first['rigAssets']['house']['assetId']
        self.uploads.clear()
        updated = self.publish('model:house')
        self.assertEqual(self.uploads, ['model:house'])
        self.assertNotEqual(updated['rigAssets']['house']['assetId'], old_house)
        self.assertEqual(updated['rigAssets']['door'], first['rigAssets']['door'])
        self.assertEqual(updated['textures'], first['textures'])
        self.assertEqual(updated['status'], 'PUBLISHED')
        self.assertEqual(self.fbx.read_bytes(), original_bytes)
        self.assertIn(old_house, [entry['asset_id'] for entry in self.store.publications(updated['slug'])])
        self.uploads.clear()
        self.publish('model')
        self.assertEqual(self.uploads, [])

    def test_retry_pending_force_scope_keeps_current_asset_id_until_success(self):
        first = self.publish('all')
        self.uploads.clear()
        self.pending_failure = True
        with self.assertRaisesRegex(TimeoutError, 'offline'):
            self.publish('model:house')
        self.assertEqual(self.store.get(first['slug'])['rigAssets']['house'], first['rigAssets']['house'])
        self.assertEqual(self.store.get(first['slug'])['status'], 'PUBLISHED')
        recovered = self.publish('model:house')
        self.assertEqual(self.uploads, ['model:house'])
        self.assertNotEqual(recovered['rigAssets']['house'], first['rigAssets']['house'])

    def test_force_scope_rejects_missing_part_without_publishing(self):
        self.publish('all')
        with self.assertRaisesRegex(ValueError, 'absent'):
            self.publish('model:fake_part')
        jobs = RealEstatePublicationJobs(self.store)
        with self.assertRaisesRegex(ValueError, 'scope'):
            jobs.start('house_level1_01', {}, scope='model:fake_part')

    def test_ui_exposes_explicit_republish_per_part(self):
        js = (ROOT / 'system/control-center/static/real-estate.js').read_text()
        self.assertIn('data-re-rig="${esc(part)}"', js)
        self.assertIn("realEstatePublish('model:'+part)", js)
        self.assertIn('window.confirm(`Republish', js)


if __name__ == '__main__':
    unittest.main()
