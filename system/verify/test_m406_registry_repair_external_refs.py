"""M406: Repair must ignore LandscapePainter scan refs when counting Deco IDs.

The real Studio repair is gated by a one-shot scan session. This suite checks
both sides of that contract: the Luau dispatch and Python transport/journal.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services.place_registry.catalog import build_catalog, validate_report
from services.place_registry.coordinator import LocationPlaceRegistry
from services.place_registry.revisions import PlaceRevisionStore


def luau(name):
    return (ROOT / 'system/studio-plugin/modules' / name).read_text('utf8')


class Assets:
    def snapshot(self):
        return {'items': [{'slug': 'ground_torch_01', 'status': 'PUBLISHED',
                           'model_asset_id': '100718497513350',
                           'texture_asset_id': '', 'appearanceMode': 'material'}]}

    def model_publication_ids(self, slug):
        return ['100718497513350']

    def mesh_id_inventory(self, slug):
        return [{'modelAssetId': '100718497513350', 'meshes': [
            {'meshId': '99710860182787', 'count': 1,
             'visualNames': ['ground_torch_01']}]}]

    def record_mesh_id_inventory(self, slug, records):
        pass


def placement(key, pid, position):
    return {'key': key, 'slug': 'ground_torch_01', 'name': 'ground_torch_01__' + pid[:8],
            'path': 'Workspace.Places.rail.ground_torch_01__' + pid[:8],
            'placementId': pid, 'modelAssetId': '100718497513350',
            'meshId': '99710860182787', 'textureId': '',
            'status': 'pending', 'needsMesh': False, 'needsRig': False,
            'needsTexture': False, 'needsStructure': True, 'duplicateId': True,
            'ambiguous': False, 'hasModel': True, 'canRepair': True,
            'canSync': False, 'issues': ['Повторяющийся Placement ID'],
            'transform': {'position': position, 'cframe': [0] * 12,
                          'size': [1, 1, 1]}}


def landscape(key):
    return {'kind': 'landscape_attachment', 'key': key, 'slug': 'ground_torch_01',
            'authorSlug': 'ground_torch_01', 'name': 'ground_torch_01_' + key,
            'path': 'Workspace.Game1LandscapeDecor.' + key,
            'ownerPath': 'Workspace.Game1LandscapeDecor', 'branchStrokeId': '',
            'anchorKind': 'branch', 'reason': 'verified external owner',
            'review': False, 'protectedFromRuntime': True, 'canSync': False,
            'needsTexture': False, 'needsOwnerCleanup': False,
            'needsPhysics': False, 'needsCollision': False}


class M406ExternalRepair(unittest.TestCase):
    def test_studio_dispatch_removes_external_refs_from_duplicate_count(self):
        dispatch = luau('StudioPlaceRegistryCommands.luau')
        repair = dispatch.split('local allRefs={}', 1)[1]
        self.assertIn('if not ref.external then table.insert(allRefs,ref) end', repair)
        self.assertIn('ctx.allRefs=allRefs', repair)
        self.assertIn('if ref.external then error("LandscapePainter authoring cannot be repaired', dispatch)
        self.assertIn('session=nil -- Mutations always invalidate', dispatch)

    def test_repair_refuses_unsafe_selection_and_incomplete_identity_evidence(self):
        repair = luau('StudioPlaceRegistryRepair.luau')
        self.assertIn('if not ref.external then', repair)
        self.assertIn('type(ref.row.placementId) ~= "string"', repair)
        self.assertIn('error("LandscapePainter does not support Place Registry Repair")', repair)
        self.assertIn('selectedIds[pid] == allIds[pid] and not retained[pid]', repair)
        self.assertIn('pid = assignedId(ctx.http, allIds)', repair)
        self.assertIn('for i = #undo, 1, -1 do pcall(undo[i]) end', repair)

    def test_real_two_duplicate_pairs_plus_external_owners_repair_scope(self):
        a = '487214ff-b21e-4ca1-8231-27b9362505f7'
        b = '553bc13e-2658-4d57-9c7e-3277ae959063'
        rows = [placement('p33', a, [398.41, -46.55, -312.98]),
                placement('p34', a, [417.90, -46.69, -313.01]),
                placement('p213', b, [356.80, -47.89, -227.20]),
                placement('p214', b, [366.40, -47.86, -218.04])]
        protected = [landscape('x1'), landscape('x2')]
        report = {'schemaVersion': 1, 'placeId': 0,
                  'placements': rows, 'protected': protected, 'warnings': []}
        assets = Assets()
        catalog = build_catalog(assets)
        self.assertEqual(len(validate_report(report, catalog)), 4)
        calls = []

        def studio(**kwargs):
            calls.append(kwargs)
            if kwargs['phase'] == 'scan':
                return {'catalogDigest': kwargs['catalog']['digest'],
                        'scanToken': 'a' * 32, 'scan': report, 'inventory': []}
            return {'operationId': 'b' * 32, 'result': {'changed': 1, 'undo': True}}

        with TemporaryDirectory() as directory:
            store = PlaceRevisionStore(directory)
            registry = LocationPlaceRegistry(assets, store, studio)
            scan = registry.operate('scan')
            self.assertEqual(scan['summary']['duplicateIds'], 4)
            self.assertEqual(len(scan['protected']), 2)
            result = registry.operate('repair', scan_token=scan['scanToken'], keys=['p33'])
            self.assertEqual(result['changed'], 1)
            self.assertEqual(calls[-1]['keys'], ['p33'])
            self.assertEqual(registry.action_journal()[0]['selected'][0]['key'], 'p33')
            self.assertEqual(len(registry.action_journal()[0]['selected']), 1)
            with self.assertRaisesRegex(ValueError, 'Scan again'):
                registry.operate('repair', scan_token=scan['scanToken'], keys=['p34'])


if __name__ == '__main__':
    unittest.main()
