"""M349 contract regression: retired static COL must not strand placed models.

Studio executes Luau; these checks catch accidental widening of the safe
historical identification rule and changes to Repair's no-transform promise.
"""
from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]
MODULES = ROOT / 'system/studio-plugin/modules'


def luau(name: str) -> str:
    return (MODULES / name).read_text('utf-8')


class RetiredStaticPlaceRegistryM349(TestCase):
    def test_static_exception_is_not_generic_mesh_subset_match(self):
        history = luau('StudioPublishedMeshHistory.luau')
        self.assertIn('function Inventory.MatchesRetiredStaticInventory(', history)
        self.assertIn('entry.legacyStaticPublication==true or staticManifest', history)
        self.assertIn('record.visualNames', history)
        self.assertIn('if retired<1 then return false end', history)
        self.assertIn('if Inventory.Id(part.MeshId)=="" then return false end', history)
        self.assertIn('if expected[record.meshId]~=record.count then return false end', history)
        self.assertIn('actualCount==expectedCount', history)
        self.assertIn('Ownership.HasNestedPlacements(placed)', history)
        self.assertIn('if claim~=nil and claim~=slug then return false end', history)
        self.assertIn('if not suffix and claim~=slug then return false end', history)
        # Existing full inventory remains the default for unrelated assets.
        self.assertIn('function Inventory.MatchesInventory(', history)
        self.assertIn('if #actual ~= #inventory.meshes then return false end', history)

    def test_registry_uses_exception_for_root_and_current_shape(self):
        inventory = luau('StudioPlaceRegistryInventory.luau')
        published = luau('StudioLocationPublishedGeometry.luau')
        self.assertIn('History.MatchesRetiredStaticInventory(candidate, version, entry)', inventory)
        self.assertIn('History.MatchesRetiredStaticInventory(root, version, entry)', published)
        self.assertIn('Published.ResolveOldVersion(entry,root,id(part.MeshId))', inventory)
        self.assertIn('canRepair=eligible and structuralState == "current" and root~=nil', inventory)
        self.assertIn('not needsMesh and not needsRig and not oldAmbiguous', inventory)
        self.assertIn('needsCollision=needsCollision', inventory)
        self.assertIn('pivotEvidence=', inventory)
        self.assertIn('meshPivotOffset={part.PivotOffset:GetComponents()}', inventory)

    def test_repair_preserves_all_preexisting_placement_transforms(self):
        repair = luau('StudioPlaceRegistryRepair.luau')
        self.assertIn('meshes[obj]={cframe=obj.CFrame,size=obj.Size,pivotOffset=obj.PivotOffset}', repair)
        self.assertIn('model:GetScale() ~= before.scale', repair)
        self.assertIn('obj.PivotOffset~=state.pivotOffset', repair)
        self.assertIn('model:GetPivot() ~= before.pivot', repair)
        self.assertIn('ctx.history:TryBeginRecording', repair)
        self.assertNotIn('model:PivotTo(', repair)
        self.assertNotIn('model:ScaleTo(', repair)
        self.assertNotIn('Instance.new("Model")', repair)

    def test_sync_stays_independent_of_repair(self):
        sync = luau('StudioPlaceRegistrySync.luau')
        self.assertIn('Collision.Prepare', sync)
        self.assertIn('RigSwap.Prepare', sync)
        self.assertIn('not ref.row.canSync or not ref.root', sync)
        self.assertIn('ref.row.needsCollision', sync)
