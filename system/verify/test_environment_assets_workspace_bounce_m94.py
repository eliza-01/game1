"""M94 hotfix contracts. Live moving/overlap physics still require Studio Play."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


def text(path):
    return (ROOT / path).read_text(encoding='utf-8')


class WorkspaceLocationAssetContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.environment = text('src/server/world/EnvironmentAssetService.luau')
        cls.collision = text('src/server/combat/WeaponEnvironmentCollision.luau')
        cls.attack = text('src/server/combat/AttackService.luau')

    def test_initial_registration_uses_workspace_not_only_default_deco_folder(self):
        self.assertIn('for _, descendant in ipairs(Workspace:GetDescendants()) do', self.environment)
        self.assertIn('scanWorkspace()', self.environment)
        self.assertNotIn('scanRoot(root)', self.environment)
        self.assertNotIn('root:GetDescendants()', self.environment)
        self.assertIn('Game1DecoAssets', self.environment)  # authoring folder remains supported

    def test_dynamic_registry_is_event_driven_for_all_workspace_descendants(self):
        self.assertIn('Workspace.DescendantAdded:Connect(', self.environment)
        self.assertIn('Workspace.DescendantRemoving:Connect(', self.environment)
        self.assertNotIn('root.DescendantAdded:Connect(', self.environment)
        self.assertNotIn('root.DescendantRemoving:Connect(', self.environment)
        self.assertIn('rebuildRegisteredModels()', self.environment)
        self.assertIn('model:IsDescendantOf(Workspace)', self.environment)

    def test_only_published_slugged_models_become_blockers(self):
        self.assertIn('Game1DecoAssetSlug', self.environment)
        self.assertIn('LocationAssetRegistry.assets[locationAssetId]', self.environment)
        self.assertIn('tostring(definition.status or "") ~= "PUBLISHED"', self.environment)
        self.assertIn('EnvironmentAssetService.ResolvePart(part)', self.collision)
        self.assertIn('definition.destructible ~= true', self.collision)
        self.assertIn('EnvironmentAssetService.GetRegisteredSnapshot()', self.collision)
        self.assertIn('revision == filterRevision', self.collision)

    def test_original_collision_probes_are_unchanged_and_always_called(self):
        self.assertIn('Workspace:Blockcast(', self.collision)
        self.assertIn('Workspace:GetPartsInPart(', self.collision)
        sweep = self.attack.split('local function applyAnimatedWeaponSweep', 1)[1].split('local function clearAttackState', 1)[0]
        self.assertIn('local environmentContact = WeaponEnvironmentCollision.Query(previousVolume, volume)', sweep)
        self.assertLess(sweep.index('WeaponEnvironmentCollision.Query(previousVolume, volume)'),
                        sweep.index('HostilePursuitRegistry.Count(character)'))
        self.assertLess(sweep.index('HostilePursuitRegistry.Count(character)'),
                        sweep.index('triggerWeaponBounce('))
        self.assertNotIn('WeaponEnvironmentBouncePolicy', self.attack)

    def test_contact_suppressed_only_when_combat_or_pursued(self):
        sweep = self.attack.split('local function applyAnimatedWeaponSweep', 1)[1].split('local function clearAttackState', 1)[0]
        self.assertRegex(sweep, r'if environmentContact then\s+local pursuerCount = HostilePursuitRegistry.Count\(character\)')
        self.assertIn('if character:GetAttribute("InCombat") == true or pursuerCount > 0 then', sweep)
        self.assertIn('else\n                    local bounced = triggerWeaponBounce(', sweep)
        self.assertLess(sweep.index('triggerWeaponBounce('), sweep.index('hitCount += applyDamageInVolume('))

    def test_registered_models_only_own_attribute_subscriptions(self):
        self.assertIn('registeredAttributeConnections[model] = model:GetAttributeChangedSignal(', self.environment)
        self.assertIn('connection:Disconnect()', self.environment)
        self.assertIn('unregisterModel(model, true)', self.environment)
        self.assertIn('EnvironmentAssetVisuals.ApplyPart(', self.environment)


if __name__ == '__main__':
    unittest.main()
