"""M379: independent house carrier ownership, publication and Studio Sync."""
from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system' / 'control-center'))
from real_estate.rig_publication_policy import (publication_analysis, carrier_bones,
    publish_bones_for_mesh, publication_fingerprint, validate_visual_weights)
from real_estate.contracts import assert_rig_survived
from real_estate.store import RealEstateStore
from real_estate.studio_sync import RealEstateStudioSync


def authored():
    bones = [
        {'name': 'chimney_01_socket', 'parent': '', 'matrixLocal': [1] * 16},
        {'name': 'house_floor_01_spawn_socket', 'parent': '', 'matrixLocal': [1] * 16},
        {'name': 'door_01_hinge_socket', 'parent': '', 'matrixLocal': [1] * 16},
        {'name': 'door_01_handle_inside_socket', 'parent': 'door_01_hinge_socket', 'matrixLocal': [1] * 16},
    ]
    def visual(name, armature='', influences=()):
        return {'name': name, 'armature': armature,
                'bones': copy.deepcopy(bones) if armature else [],
                'influencedBones': list(influences), 'vertices': 12}
    return {'schemaVersion': 1, 'meshes': [visual('chimney'), visual('roof'),
             visual('door', 'house_armature', ('door_01_hinge_socket',))]}


class IndependentCarrierContract(unittest.TestCase):
    def test_no_visual_mesh_can_own_static_socket_bones(self):
        policy = publication_analysis(authored())
        self.assertEqual([b['name'] for b in policy['carrierBones']],
            ['chimney_01_socket', 'house_floor_01_spawn_socket'])
        self.assertEqual(carrier_bones(policy), policy['carrierBones'])
        for visual in policy['meshes']:
            self.assertFalse(visual['socketCarrier'])
            if visual['name'] != 'door':
                self.assertEqual(publish_bones_for_mesh(visual), [])
        self.assertIn('door_01_hinge_socket',
            [bone['name'] for bone in next(v for v in policy['meshes'] if v['name'] == 'door')['publicationBones']])
        self.assertNotEqual(publication_fingerprint('1' * 64, carrier=True),
                            publication_fingerprint('1' * 64, carrier=False))

    def test_static_skinning_is_rejected_before_cloud_upload(self):
        invalid = authored()
        invalid['meshes'][0]['armature'] = 'house_armature'
        invalid['meshes'][0]['bones'] = copy.deepcopy(invalid['meshes'][-1]['bones'])
        invalid['meshes'][0]['influencedBones'] = ['chimney_01_socket']
        # Catalog reads must remain possible for old houses with dirty skin.
        projected = publication_analysis(invalid)
        with self.assertRaisesRegex(ValueError, 'only door_01_hinge_socket'):
            validate_visual_weights(projected)

    def test_staging_rejects_mixed_owner_and_missing_socket_bones(self):
        policy = publication_analysis(authored())
        expected_bones = carrier_bones(policy)
        carrier = {'name': 'rig_carrier', 'armature': 'house_armature',
                   'bones': expected_bones,
                   'influencedBones': [bone['name'] for bone in expected_bones]}
        visual = {'name': 'chimney', 'armature': '', 'bones': [], 'influencedBones': []}
        assert_rig_survived(policy, {'meshes': [carrier]}, 'rig_carrier')
        assert_rig_survived(policy, {'meshes': [visual]}, 'chimney')
        with self.assertRaisesRegex(ValueError, 'must contain only rig_carrier'):
            assert_rig_survived(policy, {'meshes': [carrier, visual]}, 'rig_carrier')
        with self.assertRaisesRegex(ValueError, 'must not contain rig_carrier'):
            assert_rig_survived(policy, {'meshes': [carrier, visual]}, 'chimney')
        with self.assertRaisesRegex(ValueError, 'changed bone names'):
            assert_rig_survived(policy,
                {'meshes': [{**carrier, 'bones': expected_bones[:1]}]}, 'rig_carrier')

    def test_model_publication_uses_separate_asset_and_sync_root(self):
        with tempfile.TemporaryDirectory(prefix='m379-house-store-') as directory:
            root = Path(directory)
            source = root / 'house_level5_01.fbx'
            source.write_bytes(b'fake source FBX for Store tests')
            store = RealEstateStore(root)
            with patch('real_estate.store.inspect', return_value=authored()):
                initial = store.register({'sourcePath': str(source),
                    'houseType': 'house', 'level': 5, 'variant': '01',
                    'purchasePrice': 10, 'minLevel': 1, 'salePrice': 5,
                    'textures': {}, 'textureReferences': {}})
            self.assertEqual(initial['status'], 'LOCAL_ONLY')
            self.assertNotIn('rig_carrier', initial['meshParts'])
            calls = []
            operations = {}
            def prepare(_, __, target, ___, ____, *, only_part=None):
                target.mkdir(parents=True, exist_ok=True)
                names = [only_part] if only_part else ['rig_carrier', 'chimney', 'roof', 'door']
                for name in names:
                    (target / (name + '.fbx')).write_bytes(b'mocked prepared FBX')
                calls.append(('prepare', only_part or 'all'))
            def upload(path, **kwargs):
                op = f'op{len(operations)+1}'
                operations[op] = 3000 + len(operations)
                calls.append(('upload', Path(path).stem))
                return op
            def wait(op, **kwargs):
                return SimpleNamespace(asset_id=operations[op], moderation_state='APPROVED')
            credentials = {'creatorType': 'User', 'creatorId': 1, 'apiKey': 'fake'}
            with patch('real_estate.store.prepare_publication', side_effect=prepare), \
                 patch('real_estate.store.create_model_asset', side_effect=upload), \
                 patch('real_estate.store.wait_for_operation', side_effect=wait):
                published = store.publish('house_level5_01', credentials, scope='model')
                self.assertEqual(published['status'], 'PUBLISHED')
                self.assertEqual({part for kind, part in calls if kind == 'upload'},
                                 {'rig_carrier', 'chimney', 'roof', 'door'})
                self.assertEqual(published['rigAssets']['rig_carrier']['assetId'], '3000')
                with store.connect() as db:
                    root_asset = db.execute("SELECT model_asset_id FROM real_estate WHERE slug=?",
                        ('house_level5_01',)).fetchone()[0]
                self.assertEqual(root_asset, '3000')
                before = len(calls)
                self.assertEqual(store.publish('house_level5_01', credentials,
                                               scope='model')['status'], 'PUBLISHED')
                self.assertEqual(len(calls), before, 'a retry must not duplicate cloud assets')
            loaded = []
            def loader(asset_id, dest, **kwargs):
                loaded.append((asset_id, kwargs['metadata']))
                return {'realEstateStats': {'bonesValidated': True,
                    'rigsValidated': 4, 'texturesApplied': 0, 'placedSyncVersion': 3}}
            RealEstateStudioSync(store, loader).sync('house_level5_01')
            with self.assertRaisesRegex(ValueError, 'expected v3, got 2'):
                RealEstateStudioSync(store, lambda *a, **kw: {'realEstateStats': {
                    'bonesValidated': True, 'rigsValidated': 4,
                    'texturesApplied': 0, 'placedSyncVersion': 2}}).sync('house_level5_01')
            self.assertEqual(loaded[0][0], '3000')
            self.assertEqual(loaded[0][1]['rigAssetIds']['rig_carrier'], '3000')
            self.assertEqual(loaded[0][1]['expectedCarrierBones'],
                             ['chimney_01_socket', 'house_floor_01_spawn_socket'])
            self.assertEqual(loaded[0][1]['houseAuthoringVersion'], 4)


if __name__ == '__main__':
    unittest.main()
