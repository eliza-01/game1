"""LOD Manager: read-only projection of existing Place Registry snapshots."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / 'system' / 'control-center'
sys.path.insert(0, str(HOST))

from services.location_lod_manager import LocationLodManager
from services.place_registry.revisions import PlaceRevisionStore
from api.read_world import route as read_world
from api.write_world import route as write_world


class Assets:
    def __init__(self):
        self.items = [
            {'slug': 'stone_fence_02', 'category':'fences','status':'PUBLISHED',
             'model_asset_id':'246', 'lod1':{'status':'PUBLISHED','modelAssetId':'91896785734146'}},
            {'slug': 'wooden_fence_01', 'category':'fences','status':'PUBLISHED',
             'model_asset_id':'178', 'lod1':{'status':'NOT_REGISTERED','modelAssetId':''}},
            {'slug': 'no_placement', 'category':'fences','status':'PUBLISHED',
             'model_asset_id':'123', 'lod1':{'status':'PUBLISHED','modelAssetId':'456'}},
        ]

    def snapshot(self):
        return {'items':self.items}


class Registry:
    def __init__(self, revisions):
        self.revisions = revisions
        self.calls = 0
        self.studio_mutation_counter = 0

    def operate(self, phase):
        assert phase == 'scan'
        self.calls += 1
        rev = self.revisions.add(report(), 'digest-v1')
        return {'revision': rev, 'incomplete': False}


def report():
    def placed(slug, key, name, placement_id, **flags):
        return {'slug':slug,'key':key,'name':name,'path':'Workspace/'+name,
                'placementId':placement_id,'issues':[], 'hasModel':True,
                'transform':{'cframe':[1]*12,'size':[1,1,1]}, **flags}
    return {'schemaVersion':1, 'placeId':99, 'placements':[
        placed('stone_fence_02','p1','first','uuid-1'),
        placed('stone_fence_02','p2','second','',needsCollision=True),
        placed('wooden_fence_01','p3','third','uuid-3',ambiguous=True),
    ],'warnings':[]}


class TestLocationLodManager(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.revisions = PlaceRevisionStore(self.tmp.name)
        self.assets = Assets()
        self.registry = Registry(self.revisions)
        self.manager = LocationLodManager(self.assets, self.registry)
        self.catalog = patch('services.location_lod_manager.build_catalog',
                             return_value={'digest':'digest-v1', 'items':[{'slug':a['slug']} for a in self.assets.items]})
        self.catalog.start()
        self.addCleanup(self.catalog.stop)

    def test_without_snapshot_lists_all_registered_assets(self):
        view = self.manager.overview()
        self.assertIsNone(view['snapshot'])
        self.assertEqual(view['summary']['placements'], 0)
        self.assertEqual({i['slug'] for i in view['items']}, {a['slug'] for a in self.assets.items})
        self.assertFalse(view['build']['enabled'])

    def test_scan_uses_existing_place_registry_and_persists_unchanged_snapshot(self):
        result = self.manager.scan({})
        self.assertEqual(self.registry.calls, 1)
        self.assertEqual(result['overview']['snapshot']['freshness'], 'SCANNED_THIS_SESSION')
        self.assertEqual(result['overview']['summary']['placements'], 3)
        self.assertEqual(result['overview']['summary']['missingId'], 1)
        self.assertEqual(result['overview']['summary']['ambiguous'], 1)
        self.assertEqual(result['overview']['summary']['collisionReview'], 1)
        rows = {i['slug']:i for i in result['overview']['items']}
        self.assertEqual((rows['stone_fence_02']['count'], rows['stone_fence_02']['indicator']), (2, 'yellow'))
        self.assertEqual((rows['wooden_fence_01']['count'], rows['wooden_fence_01']['indicator']), (1, 'red'))
        self.assertEqual((rows['no_placement']['count'], rows['no_placement']['indicator']), (0, 'yellow'))
        self.assertEqual(rows['stone_fence_02']['lod1ModelId'], '91896785734146')
        self.assertEqual(len(self.revisions.page()), 1)
        self.assertTrue(self.manager.scan({})['scan']['unchanged'])
        self.assertEqual(len(self.revisions.page()), 1)
        # A new instance of LOD Manager cannot know if someone edited Studio.
        self.assertEqual(LocationLodManager(self.assets,self.registry).overview()['snapshot']['freshness'],
                         'NOT_LIVE_VERIFIED')

    def test_explicit_studio_mutation_invalidates_session_freshness(self):
        self.manager.scan({})
        self.registry.studio_mutation_counter += 1
        self.assertEqual(self.manager.overview()['snapshot']['freshness'], 'NOT_LIVE_VERIFIED')

    def test_catalog_drift_and_status_change_do_not_edit_saved_snapshot(self):
        self.manager.scan({})
        with patch('services.location_lod_manager.build_catalog',
                   return_value={'digest':'new', 'items':[]}):
            view = self.manager.overview()
        self.assertEqual(view['snapshot']['freshness'], 'CATALOG_CHANGED')
        self.assertFalse(view['snapshot']['catalogMatches'])
        self.assertEqual(self.revisions.get(1)['placements'][0]['placementId'],'uuid-1')

    def test_scan_rejects_unexpected_payload_and_http_route(self):
        for payload in (None, [], {'phase':'sync'}, {'confirmDelete':True}):
            with self.assertRaises(ValueError): self.manager.scan(payload)
        deps = {'lod_manager':self.manager}
        self.assertEqual(read_world(urlsplit('/api/lod-manager'),deps,lambda:{})[0],200)
        self.assertEqual(write_world('/api/lod-manager/scan', lambda:{}, deps)[0],200)
        status, detail = write_world('/api/lod-manager/scan',lambda:{'delete':True},deps)
        self.assertEqual(status,400)
        self.assertIn('empty',detail['error'])

    def test_catalog_digest_change_creates_revision_even_if_placement_rows_are_identical(self):
        first = self.revisions.add(report(), 'digest-v1')
        second = self.revisions.add(report(), 'digest-v2')
        self.assertNotEqual(first['revisionId'], second['revisionId'])
        self.assertEqual(self.revisions.page(1)[0]['registry_digest'], 'digest-v2')

    def test_red_or_yellow_status_requires_active_publication(self):
        self.manager.scan({})
        self.assets.items[0]['lod1']={'status':'UPDATE_AVAILABLE','modelAssetId':'91896785734146'}
        view = self.manager.overview()
        self.assertEqual(next(i for i in view['items'] if i['slug']=='stone_fence_02')['indicator'],'red')
        self.assets.items[0]['lod1']={'status':'PUBLISHED','modelAssetId':'91896785734146'}
        self.assets.items[0]['lod2']={'status':'PUBLISHED','modelAssetId':'99'}
        view = self.manager.overview()
        self.assertEqual(next(i for i in view['items'] if i['slug']=='stone_fence_02')['indicator'],'green')


if __name__ == '__main__':
    unittest.main()
