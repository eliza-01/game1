"""M257: structural FBX defects must not be silently repaired on the Place."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
STUDIO = ROOT/'system/studio-plugin/modules'
UI = ROOT/'system/control-center/static'


class PublicationOnlyM257(unittest.TestCase):
    def test_plugin_excludes_structural_migration(self):
        project=json.loads((ROOT/'system/studio-plugin/plugin.project.json').read_text('utf-8'))
        self.assertNotIn('StudioLocationCarrierMigration',project['tree']['modules'])
        self.assertFalse((STUDIO/'StudioLocationCarrierMigration.luau').exists())
        repair=(STUDIO/'StudioPlaceRegistryRepair.luau').read_text('utf-8')
        self.assertNotIn('CarrierMigration',repair)
        self.assertNotIn('carrierConversions',repair)
        self.assertIn('ref.structuralState == "legacy_import_root"',repair)
        self.assertIn('Repair запрещён',repair)

    def test_inventory_marks_republication_and_never_authorizes_structural_repair(self):
        text=(STUDIO/'StudioPlaceRegistryInventory.luau').read_text('utf-8')
        self.assertIn('requiresRepublish=requiresRepublish == true',text)
        self.assertIn('canRepair=eligible and structuralState == "current"',text)
        self.assertIn('Импортный RootPart — требуется перепубликация FBX',text)
        js=(UI/'place-registry.js').read_text('utf-8')
        self.assertIn('row.canRepair === true',js)
        self.assertIn('!row.requiresRepublish',js)

    def test_find_blocks_bad_current_publication_but_allows_verified_old_rig_migration(self):
        history=(STUDIO/'StudioPublishedMeshHistory.luau').read_text('utf-8')
        sync=(STUDIO/'DecoPlacedAssetSync.luau').read_text('utf-8')
        js=(UI/'location-asset-workflow.js').read_text('utf-8')
        self.assertIn('republishRequired=republishRequired',history)
        self.assertIn('needsCanonicalReplacement=needsCanonicalReplacement',history)
        self.assertIn('!p.republishRequired',js)
        self.assertNotIn('!p.needsCanonicalReplacement',js)
        self.assertIn('Carrier.IsCanonicalPublication(row.rigManifest,row.legacyStaticPublication)',sync)
        self.assertIn('History.VerifyChildren(previousPublished,previousChildren)',sync)
        self.assertIn('RigSwap.Prepare(model, previousChildren, rigChildren(stage)',sync)
        self.assertIn('Repair не изменит скелет',js)

    def test_canonical_model_publication_still_fails_closed(self):
        author=(ROOT/'system/asset-manager/prepare_model_publication_fbx.py').read_text('utf-8')
        loader=(STUDIO/'DecoAssetLoader.luau').read_text('utf-8')
        self.assertIn('location_manifest(objects)',author)
        self.assertIn('RootPart',author)
        self.assertIn('Carrier.Validate(model, row.rigManifest, row.legacyStaticPublication)',loader)

    def test_domain_isolation(self):
        for path in ('StudioRealEstateModel.luau','CharacterTemplate.luau','StudioManagedRigSwap.luau'):
            text=(STUDIO/path).read_text('utf-8')
            self.assertNotIn('StudioLocationCarrierMigration',text)


if __name__ == '__main__':
    unittest.main()
