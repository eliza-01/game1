"""M255: runtime must not write plugin-only Location collision fidelity."""
from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[2]


class EnvironmentAssetRuntimePhysicsM255(TestCase):
    def test_environment_service_uses_runtime_safe_physics_entrypoint(self):
        service = (ROOT / 'src/server/world/EnvironmentAssetService.luau').read_text('utf-8')
        self.assertEqual(service.count('MeshPhysics.ApplyLocationModelRuntime('), 2)
        self.assertNotIn('MeshPhysics.ApplyLocationModel(', service)

    def test_runtime_entrypoint_does_not_write_collision_fidelity(self):
        core = (ROOT / 'src/shared/world/MeshPhysicsCore.luau').read_text('utf-8')
        runtime = core.split('function Core.ApplyRuntime(', 1)[1].split(
            'function Core.Apply(', 1)[0]
        authoring = core.split('function Core.Apply(', 1)[1].split(
            'local function parts(', 1)[0]

        self.assertIn('applyRuntimeProperties(mesh, canCollide, doubleSided)', runtime)
        self.assertNotIn('CollisionFidelity', runtime.split('--', 1)[0])
        self.assertIn('mesh.CollisionFidelity = Core.Fidelity(', authoring)
        self.assertIn('Core.ApplyRuntime(mesh, not noCollide, doublesided)', core)
        self.assertIn('Core.Apply(mesh, not noCollide, fidelity, doublesided)', core)


if __name__ == '__main__':
    import unittest
    unittest.main()
