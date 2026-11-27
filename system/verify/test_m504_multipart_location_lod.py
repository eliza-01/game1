"""M504 wiring and transport regression; Studio smoke covers engine geometry."""
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services.location_runtime_build import _runtime_payload
from services.location_streaming_config import DEFAULT_SETTINGS
import test_m390_location_composite_runtime as composite

def read(path):
    return (ROOT / path).read_text(encoding='utf8')

class MultipartLocationLod(unittest.TestCase):
    def test_loader_keeps_house_and_full_contracts(self):
        s=read('src/server/world/LocationLodTemplateService.luau')
        for fragment in ('allowAssembly and numberVisuals > 1 and numberVisuals <= 64', 'for _, source in ipairs(visuals)', 'assembly:SetAttribute("Game1LodPublishedPivot", publishedPivot)', 'assembly:SetAttribute("Game1LodVisualCount", numberVisuals)', 'loadPrototype(id, name, expectedParts, variant ~= "FULL")', 'loadPrototype(tonumber(spec.lod1ModelAssetId), name)', 'if numberVisuals ~= 1 then', 'not MeshPhysics.IsLocationCarrier(part)', 'not MeshPhysics.IsCollider(part.Name)'):
            self.assertIn(fragment,s)
        self.assertIn('pcall(loadPrototype, tonumber(nextId), nextId, nil, true)',read('src/server/world/StudioLodPreviewTemplates.luau'))

    def test_both_paths_use_all_parts_and_atomic_swap(self):
        s=read('src/client/world/StudioLodPreviewAdapter.luau'); r=read('src/client/world/LocationWorldStreamer.luau')
        self.assertIn('LodAssembly.Create(template, record.root:GetPivot(), record.sourceParts',s)
        self.assertNotIn('if not record.source or record.spec.lod1',s)
        for fragment in ('LodAssembly.Create(prototype, record.pivotFrame, record.fullBounds', 'transition.metadata', 'for _, component in ipairs(row.components)', 'if replacement or variant == "UNLOADED" then', 'if record.part then', 'queue:Remove(record)', 'continue', 'LocationCompositeVisual.Create', 'transition.metadata', 'record.failedAssemblies[variant] = prototype', 'record.visualCost or 1'):
            self.assertIn(fragment,r)
        self.assertIn('desired = "FULL"',s)
        self.assertEqual(r.count('RunService.Heartbeat:Connect'),1)

    def test_assembly_replication_names_and_no_physics(self):
        s=read('src/client/world/LocationLodAssembly.luau')
        for fragment in ('expected ~= count', 'Game1LodPublishedPivot', 'descriptor.relative.Rotation', 'copy.Size = descriptor.size * scale', 'local source = descriptor.source', 'metadata.sourceSize', 'metadata.sourceBase', 'metadata.parts', 'targetBase + (descriptor.relative.Position-metadata.sourceBase)*scale', 'copy.CanCollide = false', 'copy.CanQuery = false', 'copy.CanTouch = false', 'applyAppearance(copy)', 'bundle:Destroy()', 'AppearanceName'):
            self.assertIn(fragment,s)
        self.assertNotIn('Heartbeat',s)
        self.assertIn('LodAssembly.AppearanceName(mesh, asset.meshOptions)',read('src/client/world/LocationWorldStreamer.luau'))

    def test_manifest_retains_full_geometry_in_lod1(self):
        fixture=composite.CompositeRuntime('test_manifest_carries_each_visual_id_and_model_path'); fixture.setUp()
        try:
            settings={**DEFAULT_SETTINGS,'modes':{'statue_01':'lod1'}}
            data=_runtime_payload(fixture.rows,snapshot_id=160,catalog_digest='test',settings=settings)
            self.assertEqual(data['modes']['statue_01'],'lod1')
            row=data['placements'][0]; self.assertEqual(len(row['components']),3); self.assertEqual(len(row['pivot']),12)
            for component in row['components']:
                self.assertEqual(len(component['cframe']),12); self.assertEqual(len(component['size']),3)
        finally: fixture.doCleanups()

if __name__=='__main__': unittest.main()
