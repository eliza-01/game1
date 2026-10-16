"""M99 module boundaries and combat hitbox regression contracts.

These are structural checks. Actual Luau SAT/raycast results, bone motion and
EditableMesh loading still require a Roblox Studio Play test.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2] / 'src/server/combat'


def read(name):
    return (ROOT / (name + '.luau')).read_text(encoding='utf-8')


class HitboxDecompositionM99Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.facade = read('EntityHitboxService')
        cls.geometry = read('HitboxMeshGeometryCache')
        cls.builder = read('HitboxDefinitionBuilder')
        cls.frames = read('HitboxRuntimeFrames')
        cls.spatial = read('HitboxSpatialQueries')

    def test_facade_retains_published_api_without_owning_implementation(self):
        for api in (
            'function EntityHitboxService.Attach(entity: Model, visual: Model)',
            'function EntityHitboxService.Detach(entity: Model)',
            'function EntityHitboxService.QueryDamageablesInBox(',
            'function EntityHitboxService.RaycastAimRegions(',
            'function EntityHitboxService.Start()',
        ):
            self.assertIn(api, self.facade)
        for forbidden in ('CreateEditableMeshAsync', 'local function buildDefinition(',
                          'local function obbIntersects(', 'local function rayBoxDistance('):
            self.assertNotIn(forbidden, self.facade)
        self.assertIn('return table.freeze(EntityHitboxService)', self.facade)

    def test_new_modules_are_required_from_same_server_combat_folder(self):
        for module in ('HitboxMeshGeometryCache', 'HitboxDefinitionBuilder', 'HitboxSpatialQueries'):
            self.assertIn(f'require(script.Parent:WaitForChild("{module}"))', self.facade)
        self.assertIn('require(script.Parent:WaitForChild("HitboxRuntimeFrames"))', self.spatial)
        for module, code in (
            ('HitboxMeshGeometryCache', self.geometry),
            ('HitboxDefinitionBuilder', self.builder),
            ('HitboxRuntimeFrames', self.frames),
            ('HitboxSpatialQueries', self.spatial),
        ):
            self.assertIn(f'return table.freeze({module})', code)

    def test_geometry_cache_preserves_concurrent_load_and_failure_semantics(self):
        for token in (
            'local geometryCache: { [string]: any } = {}',
            'cached = geometryCache[key]',
            'while cached.state == "loading" do',
            'task.wait()',
            'geometryCache[key] = cached',
            'AssetService:CreateEditableMeshAsync(meshPart.MeshContent, { FixedSize = true })',
            'editable:GetFaceVertices(faceId)',
            'editable:GetVertexBoneWeights(vertexId)',
            'editable:GetBoneCFrame(boneId)',
            'editable:Destroy()',
            'cached.state = "failed"',
            'cached.state = "ready"',
        ):
            self.assertIn(token, self.geometry)
        self.assertNotIn('RunService.Heartbeat', self.geometry)

    def test_definition_cache_key_and_bounds_are_unchanged(self):
        for token in (
            'local definitionCache: { [string]: any } = {}',
            'scale.X,', 'scale.Y,', 'scale.Z',
            'binding.entity:GetAttribute("MonsterSlug")',
            'binding.entity:GetAttribute("NpcSlug")',
            'binding.entity:GetAttribute("CharacterArchetype")',
            'local BODY_BOX_PADDING = 0.035',
            'local HEAD_BOX_PADDING = 0.015',
            'local BROAD_RADIUS_PADDING = 0.25',
            'local MIN_BOX_AXIS = 0.05',
            'local strongest = strongestInfluence(source)',
            'headCutoffY',
            'table.sort(groupKeys)',
            'definitionCache[key] = definition',
        ):
            self.assertIn(token, self.builder)
        self.assertNotIn('CreateEditableMeshAsync', self.builder)
        self.assertNotIn('GetDescendants()', self.builder)

    def test_runtime_pose_frames_remain_cached_per_heartbeat_serial(self):
        for token in (
            'if binding.worldFrameSerial == frameSerial then',
            'binding.worldFrameSerial = frameSerial',
            'SkeletonHeadResolver.TransformedBoneFrame(bone)',
            'binding.worldHeadCFrame = anchorFrame and',
            'table.clear(frames)',
            'frames[index] = anchorFrame and',
        ):
            self.assertIn(token, self.frames)
        self.assertIn('frameSerial += 1', self.facade)
        self.assertIn('RunService.Heartbeat:Connect(function()', self.facade)

    def test_broad_phase_before_pose_refresh_and_head_prioritized(self):
        box = self.spatial.split('function HitboxSpatialQueries.BoxContact(', 1)[1].split('local function rayBoxDistance(', 1)[0]
        self.assertLess(box.index('sphereIntersectsBox('), box.index('HitboxRuntimeFrames.Refresh('))
        self.assertLess(box.index('if binding.headBox'), box.index('for index, bodyBox in ipairs(binding.bodyBoxes)'))
        for token in ('geometryRole = "head"', 'geometryRole = "body"',
                      'bestDistance = distance', 'originPosition', 'bestPosition'):
            self.assertIn(token, box)

    def test_obb_sat_and_closest_point_unchanged_in_structure(self):
        sat = self.spatial.split('local function obbIntersects(', 1)[1].split('local function sphereIntersectsBox(', 1)[0]
        self.assertEqual(sat.count('if math.abs('), 15)
        self.assertIn('local SAT_EPSILON = 1e-6', self.spatial)
        self.assertIn('boxCFrame:PointToObjectSpace(worldPoint)', self.spatial)
        self.assertIn('boxCFrame:PointToWorldSpace(Vector3.new(', self.spatial)

    def test_aim_ray_head_first_and_strict_closer_body(self):
        aim = self.spatial.split('function HitboxSpatialQueries.AimContact(', 1)[1]
        self.assertLess(aim.index('raySegmentNearSphere('), aim.index('HitboxRuntimeFrames.Refresh('))
        self.assertLess(aim.index('if binding.headBox'), aim.index('for index, bodyBox in ipairs(binding.bodyBoxes)'))
        self.assertIn('distance < bestDistance - SAT_EPSILON', aim)
        self.assertIn('rayOrigin + rayDirection * bestDistance', aim)
        self.assertIn('local direction = rayDirection / magnitude', self.facade)
        self.assertIn('if distanceLimit <= 0 or magnitude <= 1e-6 then', self.facade)

    def test_multi_target_and_studio_diagnostics_preserved(self):
        for token in (
            'for entity, binding in pairs(bindings) do',
            'entity:GetAttribute("Damageable") == true',
            'excludedTargets[entity] ~= true',
            'table.insert(results, {',
            'mode = "precomputed_bone_boxes"',
            'local previous = binding.entity:FindFirstChild(DEBUG_FOLDER_NAME)',
            'entity:SetAttribute("CombatHitboxCount", count)',
            'entity:SetAttribute("CombatTargetGeometry", "precomputed_mesh_bounds")',
            'binding.worldFrameSerial = -1',
        ):
            self.assertIn(token, self.facade)
        self.assertNotIn('DamageService', self.spatial)
        self.assertNotIn('AssetService', self.spatial)
        self.assertNotIn('Workspace:', self.spatial)


if __name__ == '__main__':
    unittest.main()
