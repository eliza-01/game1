"""M209: copying a managed Real Estate template preserves authoritative physics.

These are authoring-contract checks; the Studio clipboard needs a live Studio
regression because Python cannot emulate Roblox MeshPart cloning behavior.
"""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / 'system' / 'studio-plugin'


class RealEstateCopyPhysicsContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = (PLUGIN / 'modules/StudioRealEstateCollisionPolicy.luau').read_text(encoding='utf8')
        cls.guard = (PLUGIN / 'modules/StudioRealEstatePlacedPhysicsGuard.luau').read_text(encoding='utf8')
        cls.entry = (PLUGIN / 'Game1Bridge.server.luau').read_text(encoding='utf8')

    def test_sync_persists_policy_on_each_meshpart(self):
        for property_name in ('Game1RealEstateNoCollide',
                              'Game1RealEstateCollisionFidelity',
                              'Game1RealEstateDoubleSided'):
            self.assertIn(f'mesh:SetAttribute("{property_name}"', self.policy)
            self.assertIn(f'mesh:GetAttribute("{property_name}"', self.policy)
        self.assertIn('if not noCollide then "PreciseConvexDecomposition"', self.policy)
        self.assertIn('else FIDELITY.PreciseConvexDecomposition', self.policy)

    def test_legacy_templates_keep_collidable_geometry_precise(self):
        self.assertIn('noCollide = not mesh.CanCollide', self.policy)
        self.assertIn('mesh.CanCollide ~= not noCollide', self.policy)
        self.assertIn('mesh.CollisionFidelity ~= expected', self.policy)
        self.assertIn('Policy.Apply(mesh, mesh.Name', self.policy)

    def test_copy_guard_is_scoped_and_event_driven(self):
        self.assertIn('Workspace.DescendantAdded:Connect(onAdded)', self.guard)
        self.assertIn('RunService:IsRunning()', self.guard)
        self.assertIn('Game1RealEstateSlug', self.guard)
        self.assertIn('CollisionPolicy.RestoreCopiedMesh(descendant)', self.guard)
        self.assertIn('PlacedTargets.MarkPlaced(instance)', self.guard)
        self.assertIn('connection:Disconnect()', self.guard)
        self.assertNotIn('Heartbeat:Connect(', self.guard)
        self.assertNotIn('while true', self.guard)

    def test_registered_in_plugin_and_installer(self):
        project = json.loads((PLUGIN / 'plugin.project.json').read_text(encoding='utf8'))
        self.assertEqual(project['tree']['modules']['StudioRealEstatePlacedPhysicsGuard']['$path'],
                         'modules/StudioRealEstatePlacedPhysicsGuard.luau')
        self.assertIn('StudioRealEstatePlacedPhysicsGuard.Start(Workspace, RunService)', self.entry)
        self.assertIn('plugin.Unloading:Connect(stopEstateCopyGuard)', self.entry)
        installer = (PLUGIN / 'install.ps1').read_text(encoding='utf8')
        self.assertIn("'StudioRealEstatePlacedPhysicsGuard'", installer)


if __name__ == '__main__':
    unittest.main()
