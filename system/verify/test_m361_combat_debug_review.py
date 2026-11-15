"""M361 static contracts for debug-vs-gameplay independence and pooled FX.

Not a substitute for Studio Play/microprofiler or proving which visible effect
causes a reported screen-space spark.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def code(relative):
    return (ROOT / relative).read_text(encoding='utf8')


class CombatDebugM361(unittest.TestCase):
    def test_preview_follows_character_without_physics_queries(self):
        preview = code('src/client/dev/MeleeArcPreview.luau')
        overlay = code('src/client/dev/TestLoadoutController.luau')
        self.assertIn('RootCollider', preview)
        self.assertIn('MeleeArcDebugAnchor', preview)
        self.assertIn('Instance.new("Beam")', preview)
        self.assertIn('CanQuery = false', preview)
        self.assertNotIn('Workspace:Raycast', preview)
        self.assertNotIn('MeleeArcGeometry.Contact', preview)
        self.assertIn('RunService.RenderStepped:Connect', preview)  # aim-ray presentation
        self.assertNotIn('createAttackRadiusRing', overlay)
        self.assertIn('MeleeArcPreview.new()', overlay)
        self.assertIn('ringPreview:SetVisible(ringVisible)', overlay)

    def test_sampling_remains_visible_but_cannot_apply_damage(self):
        overlay = code('src/client/dev/TestLoadoutController.luau')
        self.assertIn('nextHitboxRenderAt = now + 1 / 8', overlay)
        self.assertIn('TARGET HITBOXES: ON · 8 Hz · #%d', overlay)
        self.assertIn('hitboxSamples += 1', overlay)
        self.assertIn('MeleeArcGeometry.Contact', overlay)
        self.assertNotIn('DamageService.Apply', overlay)
        self.assertNotIn('AttackDamageResolver.Apply', overlay)
        self.assertIn('if hitboxConnection then hitboxConnection:Disconnect() end', overlay)
        self.assertIn('targetPreview.folder:Destroy()', overlay)
        self.assertIn('ringPreview:Destroy()', overlay)

    def test_sparks_require_damage_and_ticker_is_event_driven(self):
        resolver = code('src/server/combat/AttackDamageResolver.luau')
        body = resolver.split('local finalDamage, killed = DamageService.Apply', 1)[1]
        self.assertIn('if finalDamage > 0 then', body)
        self.assertLess(body.index('if finalDamage > 0 then'), body.index('HitEffectService.Publish'))
        ticker = code('src/client/combat/effects/HitSparkPoolTicker.luau')
        self.assertIn('if connection then return end', ticker)
        self.assertIn('if slot.sparks.active then', ticker)
        self.assertIn('connection:Disconnect()', ticker)
        for name in ('HitEffectPool', 'WeaponBounceEffectPool'):
            pool = code(f'src/client/combat/effects/{name}.luau')
            self.assertIn('HitSparkPoolTicker.Create(slots)', pool)
            self.assertIn('self._startTicker()', pool)
            self.assertNotIn('RunService.RenderStepped:Connect(', pool)


if __name__ == '__main__':
    unittest.main()
