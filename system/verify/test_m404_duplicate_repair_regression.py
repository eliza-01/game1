"""M404: duplicate Placement IDs remain editable only for verified canonical placements.

Static Luau contract checks complement real Studio Edit-mode validation;
this fixture also proves two same-path placements must stay distinct by scan key.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services.place_registry.catalog import validate_report
from services.place_registry.coordinator import LocationPlaceRegistry


def source(module):
    return (ROOT / 'system/studio-plugin/modules' / module).read_text('utf8')


def row(key, pid, pos, *, collidable=False):
    return dict(key=key, slug='ground_torch_01', name='ground_torch_01__'+pid[:8],
                path='Workspace.Ladder.ground_torch_01__'+pid[:8],
                placementId=pid, modelAssetId='131758360108923',
                meshId='129094987162444', textureId='131501553365251',
                status='pending', needsMesh=False, needsRig=False,
                needsTexture=False, needsStructure=True, duplicateId=True,
                ambiguous=False, hasModel=True, canRepair=True, canSync=False,
                issues=['Повторяющийся Placement ID'],
                transform={'position':pos, 'cframe':[0]*12, 'size':[1,1,1],
                           'canCollide':collidable})


class DuplicateRepairRegression(unittest.TestCase):
    def test_same_path_different_positions_are_distinct_verified_placements(self):
        # Reproduces Snapshot #215: two pairs share BOTH a GUID and full name.
        a='487214ff-b21e-4ca1-8231-27b9362505f7'
        b='553bc13e-2658-4d57-9c7e-3277ae959063'
        rows=[row('p33',a,[398.408,-46.547,-312.978]),
              row('p34',a,[417.904,-46.694,-313.013]),
              row('p213',b,[356.799,-47.893,-227.204]),
              row('p214',b,[366.397,-47.856,-218.043])]
        result=validate_report({'schemaVersion':1,'placements':rows},
                               {'items':[{'slug':'ground_torch_01'}]})
        self.assertEqual([r['key'] for r in result],['p33','p34','p213','p214'])
        self.assertEqual(LocationPlaceRegistry._summary(result)['duplicateIds'],4)
        self.assertEqual(len({r['path'] for r in result}),2)
        self.assertEqual(len({tuple(r['transform']['position']) for r in result}),4)
        self.assertTrue(all(r['canRepair'] and not r['canSync'] for r in result))

    def test_single_duplicate_repair_does_not_skip_first_scanned_member(self):
        repair=source('StudioPlaceRegistryRepair.luau')
        self.assertIn('selectedIds[pid] == allIds[pid] and not retained[pid]',repair)
        self.assertIn('pid = assignedId(ctx.http, allIds)',repair)
        self.assertIn('Duplicate Placement ID evidence changed; rescan',repair)
        self.assertNotIn('kept[pid] ~= ref',repair)
        self.assertIn('occupied[candidate] = 1',repair)
        self.assertIn('Model pivot/PrimaryPart/parent or scale; rolling back',repair)
        self.assertIn('ctx.history:FinishRecording(recording, Enum.FinishRecordingOperation.Cancel)',repair)

    def test_sync_remains_blocked_until_new_scan_after_repair(self):
        inventory=source('StudioPlaceRegistryInventory.luau')
        commands=source('StudioPlaceRegistryCommands.luau')
        coordinator=(ROOT/'system/control-center/services/place_registry/coordinator.py').read_text('utf8')
        self.assertIn('rows[idx].canSync=false',inventory)
        self.assertIn('rows[idx].status="pending"',inventory)
        self.assertIn('session=nil -- Mutations always invalidate',commands)
        self.assertIn('if not Inventory.Validate(ref) then',commands)
        self.assertIn('self._last_scan = None',coordinator)

    def test_repair_is_metadata_only_and_external_ownership_remains_protected(self):
        repair=source('StudioPlaceRegistryRepair.luau')
        commands=source('StudioPlaceRegistryCommands.luau')
        self.assertNotIn('ApplyMesh(',repair)
        self.assertNotIn('PivotTo(',repair)
        self.assertNotIn('Instance.new(',repair)
        self.assertIn('if ref.external then error("LandscapePainter authoring cannot be repaired',commands)

if __name__=='__main__': unittest.main()
