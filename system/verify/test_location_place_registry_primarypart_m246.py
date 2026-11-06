"""M246: keep a grouping Model's PrimaryPart when wrapping one legacy mesh.

Roblox object reparenting must still be checked in Studio; this tests the
safety contract and the real persistence path for skipped repairs.
"""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services.place_registry.journal import PlaceOperationJournal
from services.place_registry.revisions import PlaceRevisionStore


class PlaceRegistryPrimaryPartM246(TestCase):
    def test_wrapper_keeps_group_primarypart_and_checks_group_pivot(self):
        src = (ROOT / 'system/studio-plugin/modules/StudioPlaceRegistryRepair.luau').read_text('utf-8')
        self.assertNotIn('part.Parent.PrimaryPart==part then\n        return false', src)
        self.assertIn('local groupPrimary=if group then group.PrimaryPart else nil', src)
        self.assertIn('local groupPivot=if group then group:GetPivot() else nil', src)
        self.assertIn('part.Parent=root', src)
        self.assertIn('group.PrimaryPart=groupPrimary', src)
        self.assertIn('group:GetPivot()~=groupPivot', src)
        self.assertIn('part.CFrame~=originalCFrame or part.Size~=originalSize', src)

    def test_wrapper_rollback_is_registered_before_reparent(self):
        src = (ROOT / 'system/studio-plugin/modules/StudioPlaceRegistryRepair.luau').read_text('utf-8')
        block = src[src.index('if not root then\n                local group='):
                    src.index('                changed+=1', src.index('if not root then\n                local group='))]
        self.assertLess(block.index('table.insert(undo,function()'), block.index('part.Parent=root'))
        self.assertLess(block.index('part.Parent=parent'), block.index('wrapper:Destroy()'))
        self.assertIn('group.PrimaryPart=groupPrimary', block)

    def test_skipped_reason_is_persisted_and_visible_in_action_log(self):
        with TemporaryDirectory() as folder:
            revisions = PlaceRevisionStore(folder)
            scan = {'schemaVersion': 1, 'placeId': 99, 'placements': []}
            before = revisions.add(scan, 'm246')['revisionId']
            journal = PlaceOperationJournal(revisions.path)
            explanation = 'p185: связи меша запрещают изменение родителя'
            journal.record(revision_id=before, place_id=99, operation_id='a'*32,
                           action='repair', selected=[{'key':'p185', 'slug':'ground_torch_01'}],
                           result={'changed': 0, 'skipped': [explanation],
                                   'note': 'Repair пропущен'})
            record = PlaceOperationJournal(revisions.path).page()[0]
            self.assertEqual(record['status'], 'no_changes')
            self.assertFalse(record['canUndo'])
            self.assertEqual(record['report']['skipped'], [explanation])
        ui = (ROOT / 'system/control-center/static/place-registry.js').read_text('utf-8')
        self.assertIn('r.report?.skipped', ui)
        self.assertIn('Причины пропуска', ui)
        self.assertIn('skipped.map(html)', ui)
