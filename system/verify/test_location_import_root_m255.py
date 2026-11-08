"""M255/M256 superseded: RootPart is a publication failure, not an in-Place Repair."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULES = ROOT / 'system/studio-plugin/modules'


class LocationRootSupersession(unittest.TestCase):
    def test_old_anchor_converter_is_gone(self):
        manifest=json.loads((ROOT/'system/studio-plugin/plugin.project.json').read_text('utf-8'))
        self.assertNotIn('StudioLocationImportRoot',manifest['tree']['modules'])
        self.assertFalse((MODULES/'StudioLocationImportRoot.luau').exists())
        loader=(MODULES/'DecoAssetLoader.luau').read_text('utf-8')
        self.assertNotIn('NormalizeFresh',loader)
        self.assertIn('Carrier.Validate(model, row.rigManifest, row.legacyStaticPublication)',loader)
        self.assertIn('PublishedRigNormalize.Apply(model, row.rigManifest)',loader)

    def test_legacy_root_never_silently_converted_on_load(self):
        loader=(MODULES/'DecoAssetLoader.luau').read_text('utf-8')
        self.assertIn('loadForMeshInventory',loader)
        self.assertIn('loadPublished',loader)
        self.assertFalse((MODULES/'StudioLocationCarrierMigration.luau').exists())
        normalizer=(MODULES/'StudioLocationPublishedRigNormalize.luau').read_text('utf-8')
        self.assertIn('model.Parent ~= nil',normalizer)
        self.assertIn('model.WorldPivot = authoredPivot',normalizer)
        self.assertIn('bone.Parent = carrier',normalizer)

    def test_structural_repair_is_blocked_and_normal_repair_remains_undoable(self):
        inv=(MODULES/'StudioPlaceRegistryInventory.luau').read_text('utf-8')
        repair=(MODULES/'StudioPlaceRegistryRepair.luau').read_text('utf-8')
        self.assertIn('CarrierRig.Diagnose',inv)
        self.assertIn('requiresRepublish',inv)
        self.assertIn('Импортный RootPart — требуется перепубликация FBX',repair)
        self.assertNotIn('CarrierMigration.Plan',repair)
        self.assertNotIn('CarrierMigration.Apply',repair)
        self.assertIn('FinishRecording(recording, Enum.FinishRecordingOperation.Cancel)',repair)

    def test_real_estate_pipeline_has_no_carrier_migration(self):
        for name in ('StudioRealEstateModel.luau','StudioManagedRigSwap.luau','CharacterTemplate.luau'):
            self.assertNotIn('StudioLocationCarrierMigration',(MODULES/name).read_text('utf-8'))


if __name__=='__main__':
    unittest.main()
