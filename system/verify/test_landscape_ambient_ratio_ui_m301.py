"""M301 regression guards for locally animated gravity/rest and scalable clip editor."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
def load(path): return (ROOT/path).read_text(encoding="utf-8")

class LandscapeAmbientM301(unittest.TestCase):
    def test_gravity_rest_uses_authored_rig_pivot_not_bounding_box_pivot(self):
        script = load('src/client/world/LandscapeSwayController.luau')
        self.assertIn('local rope = rotateAround(anchor, alignToGravity(pivot.Position - anchor))', script)
        self.assertIn('local visual = model:FindFirstChild("LandscapeSwayTarget")', script)
        self.assertIn('alignToGravity(centre - hanging.Position)', script)
        self.assertIn('state.original:Lerp(state.rest, settle)', script)
        self.assertIn('positionLine(model, state.anchor, frame.Position)', script)
        self.assertNotIn('PivotOffset =', script)
        self.assertNotIn('AssemblyLinearVelocity', script)
        self.assertNotIn('RopeConstraint', load('system/landscape-plugin/modules/LandscapeSwayAuthoring.luau'))

    def test_ambient_is_nearby_bounded_and_frame_capped(self):
        script = load('src/client/world/LandscapeSwayController.luau')
        config = load('src/shared/world/LandscapeSwayConfig.luau')
        for token in ('Config.AmbientScanSeconds','Config.AmbientMaxTargets',
                      'Config.PresentationHz','RunService.RenderStepped:Connect(tickSway)',
                      'math.sin(now * Config.AmbientFrequency + state.phase)',
                      'if not next(active) and connection then connection:Disconnect()'):
            self.assertIn(token,script)
        self.assertIn('AmbientAngle = math.rad(1.8)',config)
        self.assertIn('PresentationHz = 24',config)
        self.assertIn('AmbientMaxTargets = 48',config)

    def test_hit_and_wind_use_one_animator(self):
        client = load('src/client/world/LandscapeSwayController.luau')
        server = load('src/server/world/LandscapeSwayService.luau')
        self.assertIn('state.impact = {',client)
        self.assertIn('state.wind = {',client)
        self.assertIn('remote.OnClientEvent:Connect',client)
        self.assertIn('remote:FireClient(player, "impact", model, direction.Unit)',server)
        self.assertIn('remote:FireAllClients("wind"',server)

    def test_debug_updates_owner_animation_track(self):
        server = load('src/server/dev/MovementDebugService.luau')
        client = load('src/client/dev/MovementDebugController.luau')
        animator = load('src/client/character/animation/CharacterAnimationController.luau')
        self.assertIn('ensureRemoteEvent(remotes, "MovementDebugAnimationRatioChanged")',server)
        self.assertIn('ratioChangedRemote:FireClient(owner, model, channel, unitsPerPercent)',server)
        self.assertIn('math.abs(track.Speed) / math.max(0.01, oldScale)',server)
        self.assertIn('actualSpeed = item.sign * scale * item.multiplier',server)
        self.assertIn('ratioChangedRemote.OnClientEvent:Connect',client)
        self.assertIn('model:SetAttribute(AnimationSpeedScaling.DebugUnitsPerPercentAttribute(channel), value)',client)
        self.assertIn('CharacterAnimationController.Refresh()',client)
        self.assertIn('currentLoop:AdjustSpeed',animator) if False else self.assertIn('applyBackwardPlayback(currentLoop, slot)',animator)
        self.assertIn('track:AdjustSpeed(playbackScale)',animator)

    def test_clip_editor_paginates_saved_rules_and_is_stable_in_mature_project(self):
        js = load('system/control-center/static/animation-speed.js')
        css = load('system/control-center/static/asset-manager.css')
        self.assertIn('CUSTOM_SCALING_PAGE_SIZE=40',js)
        self.assertIn('filtered.slice(start,start+CUSTOM_SCALING_PAGE_SIZE)',js)
        self.assertIn('data-custom-row',js)
        self.assertIn('custom-scaling-filter',js)
        self.assertIn('custom-scaling-count',js)
        self.assertIn('data-custom-page="prev"',js)
        self.assertIn('data-custom-page="next"',js)
        self.assertIn('customScalingSave(aid,section,true)',js)
        self.assertIn('min-width:680px',css)
        self.assertIn('max-height:660px',css)
        self.assertNotIn('animation-speed-rule-head',js[js.index('function customScalingRender()'):])

if __name__=='__main__': unittest.main()
