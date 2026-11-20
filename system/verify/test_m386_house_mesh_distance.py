"""M386: per-mesh house visual range joins the one existing client LOD loop."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))

from real_estate.store import mesh_options


class M386HouseMeshDistance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = (ROOT / 'system/control-center/static/index.html').read_text(encoding='utf-8')
        cls.ui = (ROOT / 'system/control-center/static/real-estate.js').read_text(encoding='utf-8')
        cls.studio = (ROOT / 'system/studio-plugin/modules/StudioTextureAppearance.luau').read_text(encoding='utf-8')
        cls.client = (ROOT / 'src/client/world/LocationWorldStreamer.luau').read_text(encoding='utf-8')
        cls.policy = (ROOT / 'src/shared/world/LocationLodDistancePolicy.luau').read_text(encoding='utf-8')
        cls.model = (ROOT / 'system/studio-plugin/modules/StudioRealEstateModel.luau').read_text(encoding='utf-8')
        cls.estate = (ROOT / 'system/studio-plugin/modules/StudioRealEstateAppearance.luau').read_text(encoding='utf-8')

    def test_backend_default_only_glass_and_opt_in_other_meshes(self):
        parts = ('window_frames_glass', 'roof', 'door')
        options = mesh_options(parts, {})
        self.assertEqual(options['window_frames_glass']['loadDistanceStuds'], 50)
        self.assertTrue(options['window_frames_glass']['distanceStreaming'])
        self.assertFalse(options['roof']['distanceStreaming'])
        custom = mesh_options(parts, {'window_frames_glass': {'distanceStreaming': False},
                                    'roof': {'distanceStreaming': True, 'loadDistanceStuds': 95}})
        self.assertFalse(custom['window_frames_glass']['distanceStreaming'])
        self.assertEqual(custom['roof']['loadDistanceStuds'], 95)
        self.assertTrue(custom['roof']['distanceStreaming'])

    def test_backend_rejects_bad_values_and_does_not_corrupt_existing_mode(self):
        for invalid in (True, 19, 1001, 35.5, '50', float('nan'), None):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                mesh_options(('window_frames_glass',), {'window_frames_glass': {'loadDistanceStuds': invalid}})
        for invalid in (0, 'yes', None):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                mesh_options(('window_frames_glass',), {'window_frames_glass': {'distanceStreaming': invalid}})
        row = mesh_options(('window_frames_glass',), {'window_frames_glass': {
            'appearanceMode': 'material_atlas', 'visualMaterial': 'ForceField',
            'visualColor': '#AABBCC', 'alphaEnabled': False,
            'loadDistanceStuds': 50, 'distanceStreaming': True}})['window_frames_glass']
        self.assertEqual((row['appearanceMode'], row['visualMaterial'], row['visualColor']),
                         ('material_atlas', 'ForceField', '#AABBCC'))

    def test_ui_options_are_per_part_and_survive_save(self):
        for needle in ('realEstateState.distance=Object.fromEntries(meshNames',
                       'realEstateState.distance[part] ||= ',
                       'id="real-estate-distance-${esc(part)}"',
                       'id="real-estate-distance-studs-${esc(part)}"',
                       'distanceStreaming:realEstateState.distance[part]?.enabled===true',
                       'loadDistanceStuds:realEstateState.distance[part]?.studs??50',
                       "enabled:part==='window_frames_glass',studs:50"):
            self.assertIn(needle, self.ui)
        self.assertIn('real-estate.js?v=385a&visual=386', self.page)

    def test_studio_applies_tag_to_same_mesh_as_existing_visual_contract(self):
        self.assertIn('function StudioTextureAppearance.ApplyDistance(mesh: MeshPart, settings: any)', self.studio)
        self.assertIn('local DISTANCE_TAG = "Game1DistanceVisual"', self.studio)
        self.assertIn('CollectionService:AddTag(mesh, DISTANCE_TAG)', self.studio)
        self.assertIn('CollectionService:RemoveTag(mesh, DISTANCE_TAG)', self.studio)
        self.assertIn('StudioTextureAppearance.ApplyDistance(mesh, opts)', self.studio)
        self.assertIn('return Texture.ApplyVisual(mesh,settings)', self.estate)
        self.assertIn('StudioRealEstateAppearance.Apply(child, settings,', self.model)
        self.assertIn('StudioRealEstateAppearance.Apply(meshes[part], settings,', self.model)

    def test_one_shared_client_scheduler_not_a_second_loop(self):
        self.assertEqual(self.client.count('RunService.Heartbeat:Connect'), 1)
        self.assertEqual(self.client.count('RunService.RenderStepped:Connect'), 0)
        self.assertEqual(self.client.count('CollectionService:GetTagged(VISUAL_TAG)'), 1)
        self.assertIn('local VISUAL_INTERVAL = 1', self.client)
        self.assertIn('sampleVisuals(cameraPosition)', self.client)
        self.assertIn('if not manifest or elapsed < TICK then return end', self.client)
        self.assertIn('Policy.VisualWithin(', self.client)
        self.assertIn('part.LocalTransparencyModifier = if visible then record.original else 1', self.client)
        self.assertIn('part.CFrame:PointToObjectSpace(cameraPosition)', self.client)
        self.assertIn('function Policy.VisualWithin(distance, previous, range)', self.policy)
        self.assertIn('return Policy.WithinRange(distance, previous, range, 10)', self.policy)
        self.assertIn('if previous then return distance < range + band end', self.policy)
        self.assertIn('if not part:IsA("MeshPart") or not part:IsDescendantOf(Workspace) then return end', self.client)
        self.assertNotIn('Workspace:GetDescendants()', self.client)
        self.assertNotIn('task.wait(', self.client)
        self.assertNotIn('part:Destroy()', self.client.split('local function sampleVisuals(cameraPosition)')[1].split('end\n\nlocal function transform', 1)[0])


if __name__ == '__main__':
    unittest.main()
