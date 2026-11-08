"""M262: aliases retain placement ownership and old rigs migrate by publication swap.

Roblox CFrame/Bone mutation still requires the Studio smoke test documented in
the workflow; these tests cover executable UI grouping and cross-module safety
contracts without pretending to execute Roblox APIs in CPython.
"""
from pathlib import Path
import shutil
import subprocess
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]
MODULES = ROOT / 'system/studio-plugin/modules'


class LegacyRigMigrationM262(TestCase):
    @staticmethod
    def source(name):
        return (MODULES / name).read_text(encoding='utf-8')

    def test_eight_parts_group_as_four_placements(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('node unavailable')
        result = subprocess.run(
            [node, str(ROOT/'system/verify/location_legacy_rig_migration_m262.js')],
            cwd=ROOT, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('M262 legacy rig grouping: OK', result.stdout)

    def test_alias_is_the_same_nearest_placement_owner(self):
        owner = self.source('StudioLocationPlacementOwner.luau')
        scan = self.source('StudioPublishedMeshHistory.luau')
        store = (ROOT/'system/control-center/location_asset_store.py').read_text('utf-8')
        self.assertIn('for _, alias in ipairs(aliases or {})', owner)
        self.assertIn('Ownership.ForPart(workspace, part, slug, row.aliases)', scan)
        self.assertIn("item['aliases'] = sorted(by_current.get(item['slug'], []))", store)
        self.assertIn('local container=owner or legacyRoot or part', scan)

    def test_old_publication_is_verified_before_whole_rig_swap(self):
        sync = self.source('DecoPlacedAssetSync.luau')
        self.assertLess(sync.index('History.VerifyChildren(previousPublished,previousChildren)'),
                        sync.index('RigSwap.Prepare(model, previousChildren, rigChildren(stage),'))
        self.assertIn('stage = (published :: Model):Clone()', sync)
        self.assertIn('Geometry.Align(stage,previousPublished,model)', sync)
        self.assertNotIn('ApplyMesh(', sync)
        self.assertIn('model:SetAttribute(SLUG,slug)', sync)
        self.assertIn('model:SetAttribute(SLUG,item.oldSlug)', sync)
        self.assertIn('model.Name=item.oldName', sync)

    def test_place_registry_uses_the_same_migration_and_rollback(self):
        inventory = self.source('StudioPlaceRegistryInventory.luau')
        sync = self.source('StudioPlaceRegistrySync.luau')
        rig_swap = self.source('StudioManagedRigSwap.luau')
        self.assertIn('(claimed==entry.slug or oldClaim)', inventory)
        self.assertIn('(structuralState=="current" or (needsReplacement and oldId~=""))', inventory)
        self.assertIn('RigSwap.Prepare(root,oldParts,rigChildren(stage)', sync)
        self.assertIn('priorSlug=root:GetAttribute("Game1DecoAssetSlug")', sync)
        self.assertIn('item.ref.root:SetAttribute("Game1DecoAssetSlug",item.priorSlug)', sync)
        self.assertIn('placed root pivot, scale or parent changed; transaction rolled back', rig_swap)

    def test_ui_allows_canonical_replacement_but_not_bad_publication(self):
        ui = (ROOT/'system/control-center/static/location-asset-workflow.js').read_text('utf-8')
        self.assertNotIn('!p.needsCanonicalReplacement', ui)
        self.assertIn('!p.republishRequired&&!p.needsFbxInspection', ui)
        self.assertIn('целиком заменит подтверждённый старый дочерний rig', ui)

