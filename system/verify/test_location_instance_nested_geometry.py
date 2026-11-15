"""Regression checks: legacy grouping ownership and visual CFrame alignment.

The concrete rotation matrices below are from a read-only Place snapshot
(2026-11-15). No Studio placement is written by these tests.
"""
from __future__ import annotations

import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
BRIDGE_DIR = ROOT / 'system' / 'control-center'
sys.path.insert(0, str(BRIDGE_DIR))
from services.location_instance_manager import LocationInstanceManager
from services.studio_location_instance_bridge import run_location_instance_bridge
from test_location_instance_manager_m344 import FakeAssets

PLUGIN = (ROOT / 'system/studio-plugin/modules/StudioLocationInstanceReplace.luau').read_text(encoding='utf8')
LEGACY = (ROOT / 'system/studio-plugin/modules/StudioLocationInstanceLegacyGeometry.luau').read_text(encoding='utf8')
JS = (ROOT / 'system/control-center/static/location-instance-manager.js').read_text(encoding='utf8')


def relative_angle_degrees(first, second):
    # Physical mesh and Model rotations are orthonormal. trace(Ra^T * Rb).
    trace = sum(first[i][j]*second[i][j] for i in range(3) for j in range(3))
    return math.degrees(math.acos(max(-1.0, min(1.0, (trace-1)/2))))


class NestedLocationAndVisualGeometry(unittest.TestCase):
    def test_unpublished_container_does_not_prohibit_independent_placements(self):
        self.assertIn('local function groupingContainer(root: Model)', PLUGIN)
        self.assertIn('root:GetAttribute("Game1DecoPublishedModelAssetId") ~= nil then return false', PLUGIN)
        self.assertIn('if child:IsA("BasePart") then return false end', PLUGIN)
        self.assertIn('and not groupingContainer(ancestor) then return false', PLUGIN)
        self.assertIn('if groupingContainer(root) then return end', PLUGIN)
        self.assertIn('if owned(descendant,slug) then add(descendant) end', PLUGIN)
        self.assertIn('Location placement is nested inside a published/foreign asset:', PLUGIN)
        self.assertIn('Location placement is missing its published Model ID:', PLUGIN)
        self.assertNotIn('Nested/foreign Location model cannot be replaced', PLUGIN)

    def test_90_degree_mismatch_exists_in_authored_place_sample(self):
        # Workspace.Plots.01.land_fence.stone_fence_01__8b9b29e4
        # Model:GetPivot() rotation (near X-axis -90 roll relative to Mesh CFrame).
        model = (
            (0.2282052636, 0.9736133814, -0.0000144579),
            (-0.0000001786, -0.0000148079, -0.9999999404),
            (-0.9736132026, 0.2282052487, -0.0000032054),
        )
        mesh = (
            (0.2282052785, 0.0000145314, 0.9736134410),
            (-0.0000001786, 1.0, -0.0000148834),
            (-0.9736132622, 0.0000032226, 0.2282052636),
        )
        # Rotation of a new MeshPart matching the old Model pivot would
        # mistakenly carry over a near-90-degree error. Aligning the mesh
        # CFrames directly preserves the actual visual rotation.
        angle = relative_angle_degrees(model, mesh)
        self.assertAlmostEqual(angle, 90.0, places=2)
        self.assertAlmostEqual(relative_angle_degrees(mesh, mesh), 0.0, places=1)

    def test_geometry_mode_preserves_world_mesh_cframe_not_rebased_mesh_pivot(self):
        self.assertIn('visualFrame=old.CFrame', LEGACY)
        self.assertIn('return if anchorId == "geometry" then part.geometry else part.frame', PLUGIN)
        self.assertIn('positionAtSource(clone,old.geometry.visualFrame,anchorId,approved)', PLUGIN)
        self.assertIn('Legacy.ResizeTarget(clone,old.geometry)', PLUGIN)
        self.assertIn('if #targetVisuals == 1 then', PLUGIN)
        self.assertIn('if not state.geometry.visualFrame and approved.geometry then', PLUGIN)
        self.assertIn('expectedFrame = if command.anchorId == "geometry"', PLUGIN)
        self.assertIn('sameFrame(selectedTargetAnchor(pair.after,command.anchorId,current.approved)', PLUGIN)
        self.assertIn("options.some(option => option.id === 'geometry') ? 'geometry' : 'model'",JS)
        self.assertIn('differingVisualAxes',PLUGIN)
        self.assertIn('differingVisualAxes',JS)

    def test_server_allows_new_anchor_but_preview_remains_model(self):
        calls = []
        manager = LocationInstanceManager(FakeAssets(), lambda **kw: calls.append(kw) or {'count':1})
        base = dict(sourceSlug='stone_fence_01',targetSlug='stone_fence_02',scope='all')
        manager.operate(dict(base,phase='preview',scanToken='',anchorId='model'))
        manager.operate(dict(base,phase='replace',scanToken='a'*36,anchorId='geometry'))
        self.assertEqual([x['anchor_id'] for x in calls],['model','geometry'])
        with self.assertRaises(ValueError):
            manager.operate(dict(base,phase='preview',scanToken='',anchorId='geometry'))
        self.assertIn("anchor_id in ('model', 'geometry')", (BRIDGE_DIR / 'services/studio_location_instance_bridge.py').read_text(encoding='utf8'))


if __name__ == '__main__':
    unittest.main()
