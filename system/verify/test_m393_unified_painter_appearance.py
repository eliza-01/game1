"""M393: Location Asset Sync also handles verified LandscapePainter owners."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def src(path):
    return (ROOT / path).read_text(encoding='utf-8')


class PainterAppearanceIntegration(unittest.TestCase):
    def test_no_extra_ui_route_or_second_appearance_binder(self):
        ui = src('system/control-center/static/location-asset-workflow.js')
        self.assertIn("if(action==='replace-all')return syncAll()", ui)
        self.assertIn('const painterModel=model=>', ui)
        self.assertIn('p.painterCandidate===true', ui)
        self.assertIn("phase:'scan'", ui)
        self.assertIn("phase:'sync'", ui)
        self.assertIn("/api/location-place-registry", ui)
        self.assertIn('await refreshSyncReport()', ui)
        self.assertNotIn('open-landscape-sync', ui)
        self.assertNotIn('game1PlaceRegistryFocusAppearance', ui)
        self.assertIn('painterRows.map(p=>p.key)', ui)
        self.assertIn('scanned.incomplete', ui)
        self.assertIn('reviews.length', ui)

    def test_find_uses_explicit_painter_owner_but_never_stamps_deco_placement(self):
        hist = src('system/studio-plugin/modules/StudioPublishedMeshHistory.luau')
        self.assertIn('StudioPlaceRegistryExternalOwners', hist)
        self.assertIn('ExternalOwners.ForPart(part,workspace)', hist)
        self.assertIn('foreign.kind=="landscape_attachment"', hist)
        self.assertIn('foreign.authorSlug==slug', hist)
        self.assertIn('painterCandidate=painterRoot~=nil', hist)
        self.assertIn('local container=owner or painterRoot or legacyRoot or part', hist)
        self.assertIn('if old and not owner and not painterRoot then', hist)
        self.assertNotIn('painterRoot:SetAttribute("Game1DecoInstanceId"', hist)
        owner=src('system/studio-plugin/modules/StudioLocationPlacementOwner.luau')
        self.assertIn('ExternalOwners.ForPart(part,workspace)',owner)
        self.assertIn('if external and external.kind=="landscape_attachment" then return nil end',owner)

    def test_mutation_reuses_verified_registry_visual_and_guard(self):
        inv = src('system/studio-plugin/modules/StudioPlaceRegistryInventory.luau')
        sync = src('system/studio-plugin/modules/StudioPlaceRegistrySync.luau')
        self.assertIn('History.MatchesInventory(external.model,version)', inv)
        self.assertIn('CarrierRig.Diagnose(external.model,', inv)
        self.assertIn('PainterIntegrity.Check(external.model)', inv)
        self.assertIn('PainterIntegrity.Capture(external.model)', inv)
        self.assertIn('PainterIntegrity.AssertUnchanged(ref.integrity)', sync)
        self.assertIn('Visual.Apply(snapshot.mesh,row)', sync)
        self.assertIn('Visual.AssertCurrent(snapshot.mesh,row)', sync)
        self.assertIn('if item.external then', sync)
        self.assertIn('root:SetAttribute("Game1DecoInstanceId",nil)', sync)
        self.assertIn('item.ref.root:SetAttribute("Game1DecoInstanceId",item.ref.priorDecoInstanceId)', sync)
        self.assertIn('Visual.Restore(change)', sync)

    def test_integrity_covers_stem_tether_sway_and_nonvisual_descendants(self):
        source = src('system/studio-plugin/modules/StudioLocationPainterIntegrity.luau')
        for expected in ('LandscapeAnchorStem', 'LandscapeBranchStrokeId',
                         'LandscapeAttachmentLine', 'LandscapeSwayTarget',
                         'rig/socket changed', 'light/effect/constraint settings changed',
                         'descendant was removed', 'Game1LandscapePhysics'):
            with self.subTest(expected=expected):
                self.assertIn(expected, source)
        self.assertIn('if not descendant:IsA("SurfaceAppearance")', source)
        self.assertIn('Game1LocationCollisionOwned', source)
        self.assertIn('descendant:IsA("Fire")', source)
        self.assertIn('descendant:IsA("Light")', source)
        self.assertIn('descendant:IsA("Bone")', source)
        self.assertIn('descendant:IsA("ObjectValue")', source)
        self.assertIn('descendant:IsA("Beam")', source)
        self.assertIn('descendant:IsA("WeldConstraint")', source)
        self.assertNotIn('Instance.new(', source)
        self.assertNotIn(':Destroy()', source)
        project=src('system/studio-plugin/plugin.project.json')
        self.assertIn('modules/StudioLocationPainterIntegrity.luau', project)

    def test_cleanup_only_when_verified_and_transactionally_rollbackable(self):
        inv=src('system/studio-plugin/modules/StudioPlaceRegistryInventory.luau')
        api=src('system/control-center/services/place_registry/catalog.py')
        ui=src('system/control-center/static/location-asset-workflow.js')
        self.assertIn('needsOwnerCleanup=canAppearanceSync and needsOwnerCleanup',inv)
        self.assertIn("needs_cleanup = item.get('needsOwnerCleanup', False)",api)
        self.assertIn('not (needs_texture or needs_cleanup or needs_physics or needs_collision)',api)
        self.assertIn('p.canSync&&(p.needsTexture||p.needsOwnerCleanup||p.needsPhysics||p.needsCollision)&&p.key',ui)
        self.assertIn("phase:'sync'",ui)

    def test_registry_allows_verified_ownership_cleanup_without_texture_change(self):
        import sys
        sys.path.insert(0,str(ROOT/'system/control-center'))
        from services.place_registry.catalog import validate_report
        catalog={'items':[{'slug':'lantern_02'}]}
        row={'kind':'landscape_attachment','slug':'lantern_02','key':'x1',
             'name':'lantern_02__123','path':'Workspace.Branches.Attachments.lantern_02__123',
             'ownerPath':'Workspace.Branches.Attachments.lantern_02__123',
             'authorSlug':'lantern_02','branchStrokeId':'b1','anchorKind':'surface',
             'reason':'remove retired DecoManager stamps','review':False,
             'protectedFromRuntime':True,'canSync':True,'needsTexture':False,
             'needsOwnerCleanup':True}
        report={'schemaVersion':1,'placements':[],'protected':[row]}
        self.assertEqual(validate_report(report,catalog),[])
        for change in ({'needsOwnerCleanup':'true'},{'needsOwnerCleanup':False},
                       {'review':True},{'kind':'landscape_structure'}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                validate_report({**report,'protected':[{**row,**change}]},catalog)

    def test_opaque_atlas_always_removes_legacy_surface_appearances(self):
        binder = src('system/studio-plugin/modules/StudioTextureAppearance.luau')
        self.assertIn('if usesAlpha ~= true then', binder)
        self.assertIn('removeSurfaces(mesh)', binder)
        self.assertIn('if not enabled then return #allSurfaces == 0 end', binder)


if __name__ == '__main__':
    unittest.main()
