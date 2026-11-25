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

    def test_problem_paths_are_available_to_find_errors_in_studio(self):
        self.manager.scan({})
        rows = {item['slug']:item for item in self.manager.overview()['items']}
        problems = rows['stone_fence_02']['problemPlacements']
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0]['path'], 'Workspace/second')
        self.assertEqual(problems[0]['placementId'], '')
        self.assertEqual(rows['no_placement']['problemPlacements'], [])

    def test_managed_landscape_and_unmanaged_package_are_protected_not_placements(self):
        source = report()
        source['protected'] = [
            {'kind':'landscape_attachment','slug':'stone_fence_02',
             'path':'Workspace.Game1LandscapeDecor.Branches.Branch_a.Attachments.lantern_a',
             'ownerPath':'Workspace.Game1LandscapeDecor.Branches.Branch_a.Attachments.lantern_a',
             'name':'lantern_a','authorSlug':'stone_fence_02','branchStrokeId':'stroke-123',
             'anchorKind':'stem','reason':'LandscapePainter authored attachment',
             'review':False,'protectedFromRuntime':True},
            {'kind':'unmanaged_package','slug':'wooden_fence_01',
             'path':'Workspace.Lantern 03','ownerPath':'Workspace.Lantern 03',
             'name':'Lantern 03','authorSlug':'','branchStrokeId':'','anchorKind':'',
             'reason':'PackageLink · not a DecoManager placement',
             'review':True,'protectedFromRuntime':True},
        ]
        self.revisions.add(source, 'digest-v1')
        view = self.manager.overview()
        self.assertEqual(view['summary']['placements'], 3)
        self.assertEqual(view['summary']['protectedExternal'], 2)
        self.assertEqual(view['summary']['protectedLandscape'], 1)
        self.assertEqual(view['summary']['protectedPackages'], 1)
        self.assertEqual(view['summary']['missingId'], 1)
        a = next(i for i in view['items'] if i['slug']=='stone_fence_02')
        self.assertEqual(a['count'], 2)
        self.assertEqual(a['protectedCount'], 1)
        self.assertEqual(a['protectedOwners'][0]['kind'], 'landscape_attachment')
        b = next(i for i in view['items'] if i['slug']=='wooden_fence_01')
        self.assertEqual(b['protectedOwners'][0]['review'], True)
        self.assertEqual(self.revisions.get(1)['protected'], source['protected'])
        revised = report()
        revised['protected'] = source['protected'][:1]
        self.revisions.add(revised, 'digest-v1')
        diff = self.revisions.diff(1, 2)
        self.assertEqual((diff['added'],diff['removed']), (0,0))
        self.assertEqual((diff['protectedAdded'],diff['protectedRemoved']), (0,1))

    def test_catalog_digest_change_creates_revision_even_if_placement_rows_are_identical(self):
        first = self.revisions.add(report(), 'digest-v1')
        second = self.revisions.add(report(), 'digest-v2')
        self.assertNotEqual(first['revisionId'], second['revisionId'])
        self.assertEqual(self.revisions.page(1)[0]['registry_digest'], 'digest-v2')

    def test_catalog_modes_follow_publication_on_refresh_and_scan(self):
        from services.lod_studio_preview import snapshot
        slug = 'wooden_fence_01'
        asset = self.assets.items[1]
        self.manager.save_settings({'modes': {slug: 'full'}, 'assetDistances': {
            slug: {'lod1': 120, 'lod2': 260, 'hide': 100}}})
        before = self.manager.streaming_config.path.read_bytes()
        self.assertEqual(snapshot(self.manager)['locations'][slug]['mode'], 'full')
        asset['lod1'] = {'status': 'PUBLISHED', 'modelAssetId': '789'}
        view = self.manager.scan({})['overview']
        row = next(item for item in view['items'] if item['slug'] == slug)
        self.assertEqual(row['streamingMode'], 'lod1')
        self.assertEqual(row['resolvedStreamingMode'], 'lod1')
        self.assertEqual(view['settings']['modes'][slug], 'lod1')
        self.assertEqual(row['distances'], {'lod1': 79, 'lod2': 260, 'hide': 100})
        self.assertEqual(snapshot(self.manager)['locations'][slug]['distances'], row['distances'])
        # Automatic projection does not rewrite authored distances on refresh.
        self.assertEqual(self.manager.streaming_config.path.read_bytes(), before)
        asset['lod2'] = {'status': 'PUBLISHED', 'modelAssetId': '790'}
        self.assertEqual(self.manager.overview()['settings']['modes'][slug], 'lod2')
        self.assertEqual(snapshot(self.manager)['locations'][slug]['mode'], 'lod2')
        asset['lod1']['status'] = 'UPDATE_AVAILABLE'
        self.assertEqual(snapshot(self.manager)['locations'][slug]['mode'], 'full')
        asset['lod1'] = {'status': 'PUBLISHED', 'modelAssetId': 'bad'}
        self.assertEqual(snapshot(self.manager)['locations'][slug]['mode'], 'full')
        asset['lod1'] = {'status': 'PUBLISHED', 'modelAssetId': '789'}
        self.manager.save_settings({'modes': {slug: 'off'}})
        self.assertEqual(snapshot(self.manager)['locations'][slug]['mode'], 'off')
        row = next(item for item in self.manager.scan({})['overview']['items'] if item['slug'] == slug)
        self.assertEqual(row['streamingMode'], 'off')
        self.assertEqual(row['availableStreamingMode'], 'lod2')
        self.manager.save_settings({'modes': {slug: 'full'}})
        self.assertEqual(self.manager.streaming_config.read()['modes'][slug], 'lod2')

    def test_new_unplaced_asset_with_published_lod_is_automatic(self):
        row = next(item for item in self.manager.overview()['items'] if item['slug'] == 'no_placement')
        self.assertEqual(row['count'], 0)
        self.assertEqual(row['streamingMode'], 'lod1')
        self.assertFalse(row['streamingEligible'])

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

class TestLodManagerSettingsRoutes(unittest.TestCase):
    def test_saving_settings_uses_project_root_and_revokes_preflight(self):
        from unittest.mock import Mock
        import tempfile
        from services.location_streaming_config import DEFAULT_SETTINGS
        with tempfile.TemporaryDirectory() as folder:
            revisions=PlaceRevisionStore(folder)
            manager=LocationLodManager(Assets(), Registry(revisions))
            with patch('services.location_lod_manager.build_catalog',
                       return_value={'digest':'digest-v1','items':[{'slug':'stone_fence_02'}]}):
                manager._preflight=('old_token','a'*64,10,'digest')
                status, view=write_world('/api/lod-manager/settings',lambda:{'modes':{'stone_fence_02':'full'}},
                                         {'lod_manager':manager})
                self.assertEqual(status,200)
                self.assertIsNone(manager._preflight)
                self.assertEqual(view['settings']['modes']['stone_fence_02'],'lod1')
                self.assertTrue(manager.streaming_config.path.exists())
                error_status, error=write_world('/api/lod-manager/settings',
                    lambda:{'modes':{'imaginary_slug':'full'}},{'lod_manager':manager})
                self.assertEqual(error_status,400)
                self.assertIn('Unknown',error['error'])
                self.assertEqual(manager.streaming_config.read()['modes']['stone_fence_02'],'lod1')
