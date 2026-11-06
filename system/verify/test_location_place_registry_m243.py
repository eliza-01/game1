"""M243: group Sync command and shared Location placement ownership contract."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / 'system/studio-plugin'
STATIC = ROOT / 'system/control-center/static'


class M243LocationOwnership(TestCase):
    def source(self, name: str) -> str:
        return (PLUGIN / 'modules' / name).read_text(encoding='utf8')

    def test_same_owner_resolver_drives_find_and_scoped_sync(self):
        helper = self.source('StudioLocationPlacementOwner.luau')
        find = self.source('StudioPublishedMeshHistory.luau')
        sync = self.source('DecoPlacedAssetSync.luau')
        manifest = json.loads((PLUGIN / 'plugin.project.json').read_text('utf8'))
        self.assertEqual(manifest['tree']['modules']['StudioLocationPlacementOwner']['$path'],
                         'modules/StudioLocationPlacementOwner.luau')
        self.assertIn("'StudioLocationPlacementOwner'", (PLUGIN / 'install.ps1').read_text('utf8'))
        self.assertIn('function Owner.ForPart(workspace:', helper)
        self.assertIn('Ownership.ForPart(workspace, part, slug)', find)
        self.assertIn('Ownership.ForPart(workspace, part, slug)', sync)
        self.assertIn('if not selectedOwner or not chosenRoots[selectedOwner]', sync)
        # The old Find-nearest/Sync-topmost conflict must never return.
        self.assertNotIn('if not nested then table.insert(found, descendant)', sync)
        self.assertNotIn('scanned Location instance no longer exists; rescan', sync)

    def test_ownership_never_leaks_through_other_stamped_roots(self):
        helper = self.source('StudioLocationPlacementOwner.luau')
        self.assertIn('return nil', helper)
        self.assertIn('if cursor:IsA("Model") and (cursor:GetAttribute(SLUG) ~= nil', helper)
        self.assertIn('cursor:GetAttribute(SLUG) == slug', helper)
        self.assertIn('cursor:GetAttribute(INSTANCE)', helper)
        self.assertIn('part:IsDescendantOf(authoring)', helper)
        self.assertIn('part:IsDescendantOf(camera)', helper)

    def test_nested_placement_is_never_swapped_into_parent_rig(self):
        helper = self.source('StudioLocationPlacementOwner.luau')
        sync = self.source('DecoPlacedAssetSync.luau')
        self.assertIn('Owner.HasNestedPlacements', helper)
        self.assertIn('Ownership.HasNestedPlacements(model)', sync)
        self.assertLess(sync.index('Ownership.HasNestedPlacements(model)'),
                        sync.index('RigSwap.Prepare(model, previousChildren, rigChildren(stage),'))
        self.assertIn('no Place geometry modified', sync)

    def test_group_sync_uses_normal_scoped_sync_and_preserves_global_sync(self):
        source = (STATIC / 'place-registry.js').read_text(encoding='utf8')
        self.assertIn('data-pr-action="sync-group"', source)
        self.assertIn('Sync group (${syncs})', source)
        self.assertIn('data-pr-blocked="${syncs===0}"', source)
        self.assertIn("phase==='repair-group'||phase==='sync-group'", source)
        self.assertIn("mutate(isRepair?'repair':'sync',keys", source)
        self.assertIn("'pr-sync-all'", source)
        node = shutil.which('node')
        if node:
            process = subprocess.run([node, str(ROOT/'system/verify/location_place_registry_group_sync_m243.js')],
                                     capture_output=True, text=True, timeout=20)
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)

    def test_real_estate_edit_sync_services_still_separate(self):
        visual = self.source('StudioRealEstatePlacedVisualSync.luau')
        sync = self.source('DecoPlacedAssetSync.luau')
        self.assertIn('StudioManagedRigSwap', visual)
        self.assertIn('StudioManagedRigSwap', sync)
        self.assertNotIn('StudioLocationPlacementOwner', visual)
        self.assertNotIn('PlaceRegistry', visual)
