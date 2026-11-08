"""M252 regression guards: published rig identity, additive COL and action reports.

Static Luau checks complement real persistence/transport tests; only a Roblox
Studio Edit-mode test can validate actual MeshPart cloning and Undo behaviour.
"""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services.place_registry.catalog import validate_report
from services.place_registry.coordinator import LocationPlaceRegistry
from services.place_registry.revisions import PlaceRevisionStore


def source(name):
    return (ROOT / 'system/studio-plugin/modules' / name).read_text('utf8')


class PublicationReconciliationM252(unittest.TestCase):
    def test_original_campfire_inventory_demonstrates_the_bug(self):
        old = {'modelAssetId': '119790979739015', 'meshes': [
            {'meshId': '70451663424090', 'count': 1, 'visualNames': ['campfire_01']}]}
        new = {'modelAssetId': '85955870892092', 'meshes': [
            {'meshId': '119159216521971', 'count': 1, 'visualNames': []},
            {'meshId': '70451663424090', 'count': 1, 'visualNames': ['campfire_01']}]}
        self.assertEqual(old['meshes'][0]['meshId'], new['meshes'][1]['meshId'])
        self.assertNotEqual({i['meshId']: i['count'] for i in old['meshes']},
                            {i['meshId']: i['count'] for i in new['meshes']})

    def test_publication_resolver_requires_full_multiset_and_verified_stamp(self):
        policy = source('StudioLocationPublishedGeometry.luau')
        self.assertIn('History.MatchesInventory(root, version)', policy)
        self.assertIn('History.MatchesInventory(root, version)', policy)
        self.assertIn('if #matches == 1 then return matches[1], false end', policy)
        self.assertIn('Game1DecoPublishedModelAssetId', policy)
        self.assertIn('if candidate == stamped then return candidate, false end', policy)
        self.assertIn('return "", true', policy)
        inventory = source('StudioPlaceRegistryInventory.luau')
        self.assertIn('Published.ResolveOldVersion(entry,root,id(part.MeshId))', inventory)
        self.assertIn('not Published.CurrentShape(entry,root)', inventory)
        self.assertIn('needsRig=needsRig', inventory)
        self.assertNotIn('local function versionFor(', inventory)

    def test_scan_rejects_new_unscanned_colliders_and_changed_group_pivot(self):
        inventory=source('StudioPlaceRegistryInventory.luau')
        self.assertIn('meshStates=meshStates',inventory)
        self.assertIn('if not ref.meshStates[child] then return false end',inventory)
        self.assertIn('root:GetPivot()~=ref.rootPivot',inventory)
        self.assertIn('seen~=expected',inventory)

    def test_repair_cannot_reconstruct_published_collider_or_skeleton(self):
        repair = source('StudioPlaceRegistryRepair.luau')
        self.assertNotIn('restoreCol(', repair)
        self.assertNotIn('Instance.new("MeshPart")', repair)
        self.assertNotIn('Instance.new("Model")', repair)
        self.assertNotIn('CarrierMigration', repair)
        self.assertIn('требуется перепубликация FBX', repair)
        self.assertIn('не через Repair', repair)

    def test_repair_is_identity_only_and_idempotent(self):
        repair = source('StudioPlaceRegistryRepair.luau')
        self.assertIn('not ref.row.needsStructure and not ref.row.duplicateId', repair)
        self.assertIn('if dirty then', repair)
        self.assertIn('changed += 1', repair)
        self.assertIn('Model pivot/PrimaryPart/parent', repair)
        self.assertNotIn('Physics.ApplyLocationSurfaceMaterial', repair)
        self.assertIn('changed = 0, skipped = blocked', repair)
        self.assertIn('FinishRecording(recording, Enum.FinishRecordingOperation.Cancel)', repair)

    def test_sync_distinguishes_rig_material_and_alpha_and_reports_skips(self):
        sync = source('StudioPlaceRegistrySync.luau')
        self.assertIn('ref.row.needsMesh or ref.row.needsRig', sync)
        self.assertIn('ref.row.needsTexture or ref.row.needsMaterial or ref.row.needsAlpha', sync)
        self.assertIn('note=if #blocked>0', sync)
        self.assertIn('RigSwap.Prepare', sync)
        self.assertIn('RigSwap.Rollback', sync)
        self.assertIn('Physics.ApplyLocationSurfaceMaterial(root,ref.entry.material', sync)

    def test_api_rig_flag_is_validated_and_summary_counts_it(self):
        row = {'key': 'p1', 'slug': 'campfire_01', 'name': 'campfire_01__one',
               'path': 'Workspace.campfire_01__one', 'meshId': '70451663424090',
               'textureId': '78602158656399', 'placementId': 'abc', 'status': 'pending',
               'needsMesh': False, 'needsRig': True, 'needsTexture': False,
               'needsStructure': True, 'duplicateId': False, 'ambiguous': False,
               'hasModel': True, 'canSync': False, 'issues': ['Нет обязательного COL-меша'],
               'transform': {}}
        catalog = {'items': [{'slug': 'campfire_01'}]}
        report = {'schemaVersion': 1, 'placements': [row]}
        self.assertEqual(validate_report(report, catalog), [row])
        self.assertEqual(LocationPlaceRegistry._summary([row])['outdatedMesh'], 1)
        row['needsRig'] = 'true'
        with self.assertRaisesRegex(ValueError, 'needsRig'):
            validate_report(report, catalog)

    def test_noop_journal_retains_skip_reason_and_no_undo(self):
        from services.place_registry.journal import PlaceOperationJournal
        with TemporaryDirectory() as tmp:
            registry=PlaceRevisionStore(tmp)
            rev=registry.add({'schemaVersion': 1, 'placeId': 0, 'placements': []}, 'm252')['revisionId']
            journal=PlaceOperationJournal(registry.path)
            journal.record(revision_id=rev, place_id=0, operation_id='f'*32,
                           action='sync', selected=[{'key':'p1', 'slug':'campfire_01', 'name':'one'}],
                           result={'changed':0,'skipped':['p1: требуется Repair COL']})
            item=journal.page()[0]
            self.assertEqual(item['status'],'no_changes')
            self.assertFalse(item['canUndo'])
            self.assertIn('Repair COL',item['report']['skipped'][0])


if __name__ == '__main__': unittest.main()
