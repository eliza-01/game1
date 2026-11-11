"""M278: atlas binding revisions are not proof that Place needs Studio Sync."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))

from services.location_studio_sync_verification import classify_scan
from api.write_world import route


def part(*, mesh=True, texture=True, alpha=True, managed=True, blocked=False):
    return dict(managed=managed, meshCurrent=mesh, textureCurrent=texture,
                alphaCurrent=alpha, needsMesh=not mesh, needsTexture=not texture,
                needsAlpha=not alpha, republishRequired=blocked,
                needsFbxInspection=False, needsCanonicalReplacement=False)


def scan_report(*, parts=None, mode='current', unmanaged=0, geometry=0):
    items = [] if parts is None else parts
    return dict(mode=mode,parts=items,unmanagedMeshParts=unmanaged,
                managedMeshParts=sum(item['managed'] for item in items),
                managedModels=int(any(item['managed'] for item in items)),
                meshPending=sum(item['managed'] and item['needsMesh'] for item in items),
                texturePending=sum(item['managed'] and item['needsTexture'] for item in items),
                alphaPending=sum(item['managed'] and item['needsAlpha'] for item in items),
                geometryPending=geometry,
                inventory=[dict(modelAssetId='12345',meshes=[])])


class FakeAtlas:
    def __init__(self):
        self.ack = []
    def binding(self, *_args):
        return {'revision': 2, 'variant_id': 11}
    def mark_synced(self, *args):
        self.ack.append(args)
        return True


class FakeAssets:
    def __init__(self):
        self.atlases = FakeAtlas()
        self.row = dict(slug='ivy_02',model_asset_id='12345',
                        model_published_sha256='deadbeef',texture_asset_id='67890',
                        bindingRevision=2,revision=4,alphaEnabled=False)
        self.exported = 0
        self.inventory = []
        self.changed_on_second_get = False
        self.gets = 0
    def get(self, slug):
        self.gets += 1
        result = dict(self.row)
        if self.changed_on_second_get and self.gets > 1:
            result['model_asset_id'] = '22222'
        return result
    def model_publication_ids(self, _slug):
        return ['12345']
    def mesh_id_inventory(self, _slug):
        return []
    def record_mesh_id_inventory(self, slug, records):
        self.inventory.append((slug, records))
    def export(self):
        self.exported += 1


class LocationStudioSyncVerifiedStatusM278(unittest.TestCase):
    def test_no_geometry_placed_needs_no_replace(self):
        self.assertEqual(classify_scan(scan_report()), 'current')

    def test_current_managed_copy_needs_no_replace(self):
        self.assertEqual(classify_scan(scan_report(parts=[part()])), 'current')

    def test_actual_mesh_texture_alpha_differences_are_pending(self):
        for kw, mode in (({'mesh': False}, 'mesh'),
                         ({'texture': False}, 'texture'),
                         ({'alpha': False}, 'alpha')):
            with self.subTest(kw=kw):
                self.assertEqual(classify_scan(scan_report(parts=[part(**kw)], mode=mode,
                                        geometry=int(kw.get('mesh') is False))), 'pending')

    def test_unmanaged_or_uncanonical_prevents_automatic_ack(self):
        self.assertEqual(classify_scan(scan_report(parts=[part(managed=False)],unmanaged=1)),
                         'review_required')
        self.assertEqual(classify_scan(scan_report(parts=[part(blocked=True)],mode='mesh',geometry=1)),
                         'review_required')
        self.assertEqual(classify_scan(scan_report(parts=[part()],geometry=1)), 'review_required')
        self.assertEqual(classify_scan({'mode':'current','parts':[]}), 'review_required')
        legacy = part()
        del legacy['alphaCurrent']
        self.assertEqual(classify_scan(scan_report(parts=[legacy])), 'review_required')

    def request(self, report, *, modified_mid_scan=False):
        assets = FakeAssets()
        assets.changed_on_second_get = modified_mid_scan
        deps = defaultdict(lambda:None, dict(location_assets=assets,
            sync_location_assets_to_studio=lambda **_: report,
            location_asset_sync_history=None))
        status, response = route('/api/location-assets/studio-sync',
            lambda: {'slug':'ivy_02','phase':'scan'}, deps)
        return status, response, assets

    def test_read_only_scan_can_ack_complete_current_place(self):
        for items in ([], [part()]):
            with self.subTest(placements=len(items)):
                status, response, assets = self.request(scan_report(parts=items))
                self.assertEqual(status, 200, response)
                self.assertEqual(response['studio']['verification'], 'current')
                self.assertEqual(assets.atlases.ack, [('location_asset','ivy_02',2)])
                self.assertEqual(assets.exported, 1)
                self.assertEqual(len(assets.inventory), 1)

    def test_changed_or_unmanaged_places_do_not_ack(self):
        cases = [
            (scan_report(parts=[part(texture=False)],mode='texture'), 'pending'),
            (scan_report(parts=[part(managed=False)],unmanaged=1), 'review_required'),
            (scan_report(parts=[part(blocked=True)],mode='mesh',geometry=1), 'review_required'),
        ]
        for report, verdict in cases:
            with self.subTest(verdict=verdict):
                status, response, assets = self.request(report)
                self.assertEqual(status, 200, response)
                self.assertEqual(response['studio']['verification'], verdict)
                self.assertEqual(assets.atlases.ack, [])
                self.assertEqual(assets.exported, 0)

    def test_concurrent_publication_must_not_be_acknowledged(self):
        status, response, assets = self.request(scan_report(), modified_mid_scan=True)
        self.assertEqual(status, 200, response)
        self.assertEqual(response['studio']['verification'], 'review_required')
        self.assertEqual(assets.atlases.ack, [])


if __name__ == '__main__':
    unittest.main()
