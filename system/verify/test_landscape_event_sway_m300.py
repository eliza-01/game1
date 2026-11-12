"""M300: anchored event-only sway; must not recreate the native-physics stack."""
from pathlib import Path
import json
import unittest

ROOT=Path(__file__).resolve().parents[2]

def load(name):return (ROOT/name).read_text(encoding='utf-8')

class EventSwayM300(unittest.TestCase):
    def test_authoring_uses_event_assembly_and_removes_old_writer(self):
        project=json.loads(load('system/landscape-plugin/plugin.project.json'))
        names=project['tree']['modules']
        self.assertIn('LandscapeSwayAuthoring',names)
        self.assertNotIn('LandscapeTetherPhysics',names)
        self.assertFalse((ROOT/'system/landscape-plugin/modules/LandscapeTetherPhysics.luau').exists())
        source=load('system/landscape-plugin/modules/LandscapeSwayAuthoring.luau')
        self.assertIn('instance:GetAttribute(GENERATED) == true',source)
        self.assertIn('part.Anchored = true',source)
        self.assertIn('part.CanQuery = true',source)
        for forbidden in ('Instance.new("RopeConstraint")','Instance.new("BallSocketConstraint")',
                          'Instance.new("LinearVelocity")','Instance.new("WeldConstraint")'):
            self.assertNotIn(forbidden,source)
    def test_hit_proxy_is_distinct_from_real_collision(self):
        source=load('system/landscape-plugin/modules/LandscapeSwayAuthoring.luau')
        self.assertIn('part.Name = TARGET',source)
        self.assertIn('part.CanCollide = false',source)
        self.assertIn('part.CanTouch = false',source)
        self.assertIn('part.Transparency = 1',source)
        self.assertIn('part.CFrame = pivot * CFrame.new',source)
        self.assertNotIn('part.PivotOffset =',source)
    def test_profile_migrates_old_checkbox_only_at_decode(self):
        source=load('system/landscape-plugin/modules/LandscapeProfiles.luau')
        self.assertIn('settings.physicsEnabled == true',source)
        self.assertIn('swayEnabled = swayEnabled',source)
        self.assertNotIn('physicsEnabled = physicsEnabled',source)
    def test_impact_authority_remains_on_server(self):
        server=load('src/server/world/LandscapeSwayService.luau')
        arrow=load('src/server/combat/BowProjectileService.luau')
        attack=load('src/server/combat/AttackService.luau')
        self.assertIn('function Service.Impact(',server)
        self.assertIn('function Service.Melee(',server)
        self.assertIn('function Service.Wind(',server)
        self.assertIn('RemoteEvent',server)
        self.assertIn('GetPartBoundsInBox',server)
        self.assertIn('LandscapeSwayService.Impact(',arrow)
        self.assertIn('LandscapeSwayService.Melee(',attack)
        self.assertNotIn('OnServerEvent',server)
    def test_client_updates_only_active_sway_models(self):
        controller=load('src/client/world/LandscapeSwayController.luau')
        self.assertIn('RunService.RenderStepped:Connect(tickSway)',controller)
        self.assertIn('connection:Disconnect()',controller)
        self.assertIn('model:PivotTo(frame)',controller)
        self.assertIn('LandscapeAttachmentLine',controller)
        self.assertIn('elseif event == "wind"',controller)
        # M301 discovers streamed pendulums at a low fixed cadence; the
        # visual render connection still disconnects outside populated zones.
        self.assertIn('task.wait(Config.AmbientScanSeconds)',controller)
        self.assertIn('if not next(active) and connection then connection:Disconnect()',controller)
    def test_server_enforces_anchored_world(self):
        source=load('src/server/world/EnvironmentAssetService.luau')
        self.assertNotIn('isNativeLandscapeSuspension',source)
        self.assertIn('descendant.Anchored = true',source)
    def test_bootstrap_registers_both_services(self):
        self.assertIn('LandscapeSwayService',load('src/server/bootstrap/ServiceCatalog.luau'))
        self.assertIn('LandscapeSwayController',load('src/client/init.client.luau'))

if __name__=='__main__':unittest.main()
