"""M360: HitEnd is a single authoritative action event; graphics are optional.

Source/runtime-data contracts only. Studio Play is required for Roblox physics and
loaded/missing AnimationTrack behavior; these tests do not emulate Roblox.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def src(name: str) -> str:
    return (ROOT / name).read_text(encoding='utf-8')


class HitEndActionM360(unittest.TestCase):
    def test_authored_hitend_is_independent_of_hitstart_and_track_length(self):
        source = src('src/shared/combat/CharacterAttackHitEnd.luau')
        timeline = src('src/shared/combat/AttackTimelineConfig.luau')
        self.assertIn('timing.events.HitEnd', source)
        self.assertNotIn('events.HitStart', source)
        self.assertNotIn('AnimationTrack', source)
        self.assertNotIn('HitStart.time', source)
        self.assertIn('return table.freeze({ time = time })', source)
        self.assertIn('sourceTime / playbackSpeed', timeline)
        self.assertIn('gameplayDuration = CharacterAttackCadence.DurationForStat(statValue)', timeline)

        rows = json.loads((ROOT / 'assets/manifests/attack-timelines.json').read_text())['timelines']
        for row in rows:
            if not row['clipId'].startswith('human_') or 'HitEnd' not in row['events']:
                continue
            fraction = row['events']['HitEnd']['normalizedTime']
            for attack_speed in (100, 200, 400):
                duration = 3.0 * 100 / attack_speed
                playback = duration - 0.03
                self.assertGreaterEqual(fraction * playback, 0)
                self.assertLess(fraction * playback, duration)
                # An absent/incorrect rendered track never changes authored time.
                for visual_track_length in (0, .1, 1.5, 7):
                    self.assertAlmostEqual(fraction * playback, fraction * (duration - 0.03))

    def test_single_server_event_and_exactly_once_damage_snapshot(self):
        server = src('src/server/combat/AttackService.luau')
        store = src('src/server/combat/AttackSessionStore.luau')
        hit = src('src/server/combat/AttackDamageResolver.luau')
        self.assertIn('CharacterAttackHitEnd.Resolve(timing)', server)
        self.assertEqual(server.count('task.delay(hitEndEvent.time, function()'), 1)
        self.assertEqual(server.count('applyMeleeArc(player, character, currentRoot'), 1)
        self.assertNotIn('MeleeSampleInterval', server)
        self.assertNotIn('task.wait(', server)
        self.assertNotIn('AttackWeaponPose', server)
        self.assertNotIn('AttackDamageStartsAt', server)
        self.assertNotIn('AttackDamageEndsAt', server)
        self.assertIn('or character:GetAttribute("LifeState") ~= "Alive" then return end', server)
        self.assertIn('session.serial ~= serial', server)
        self.assertIn('AttackSessionStore.MarkMeleeResolved(player, character, serial, clientAttackId)', server)
        self.assertIn('session.hitResolved = true', store)
        self.assertIn('or session.environmentBlocked or session.hitResolved', server)
        self.assertIn('MeleeTargetQuery.Find', hit)
        self.assertIn('DamageService.Apply', hit)
        self.assertNotIn('hitTargets', store)
        self.assertNotIn('damageWindow', store)
        self.assertNotIn('query.hitTargets', hit)
        self.assertIn('active.untilTime - os.clock()', server)
        self.assertIn('source=melee_arc HitEnd', server)

    def test_animation_is_not_a_precondition_of_gameplay(self):
        visual = src('src/client/character/animation/CharacterAnimationController.luau')
        client = src('src/client/combat/AttackController.luau')
        accepted_at = visual.index('local actionStartedAt = os.clock()', visual.index('function CharacterAnimationController.PlayAction'))
        compose = visual.index('task.spawn(function()', accepted_at)
        returned = visual.index('durationSeconds = runtimeDuration,', compose)
        self.assertLess(accepted_at, compose)
        self.assertLess(compose, returned)
        self.assertIn('visual unavailable; gameplay continues', visual)
        self.assertIn('if not character or lifeTransition then return nil end', visual)
        self.assertIn('Animator missing; visual unavailable, gameplay continues', visual)
        self.assertIn('track = nil, -- may load later', visual)
        self.assertIn('track.TimePosition = math.min(', visual)
        self.assertNotIn('cancelled; upper-body composition unavailable', visual)
        self.assertIn('local action = animationController.PlayAction("attack")', client)
        self.assertIn('attack:FireServer({', client)
        self.assertIn('hitEndEvent.time', client)

    def test_authoring_has_only_hitend_and_strips_historical_start(self):
        import importlib.util
        module_path = ROOT / 'system/control-center/timeline_store.py'
        spec = importlib.util.spec_from_file_location('m360_timeline_store', module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.event_names_for_subject('characters', '1hs'), {'HitEnd'})
        self.assertEqual(module.event_names_for_subject('characters', 'bow'), {'Release'})
        self.assertEqual(module.event_names_for_subject('monsters'), {'Hit'})
        events = module.TimelineStore._validate_events('characters', {
            'HitStart': {'normalizedTime': 0.2},
            'HitEnd': {'normalizedTime': 0.7},
        })
        self.assertEqual(events, {'HitEnd': {'normalizedTime': 0.7}})
        self.assertNotIn('"HitStart"', src('system/control-center/static/timelines.js'))
        manifest = json.loads((ROOT / 'assets/manifests/attack-timelines.json').read_text())
        for row in manifest['timelines']:
            if 'HitEnd' in row['events']:
                self.assertEqual(set(row['events']), {'HitEnd'})
        runtime = src('src/shared/combat/AttackTimelineData.luau')
        self.assertNotIn('HitStart = table.freeze', runtime)

    def test_debug_preview_is_bounded_and_melee_aim_updates_stop_at_hitend(self):
        overlay = src('src/client/dev/TestLoadoutController.luau')
        client = src('src/client/combat/AttackController.luau')
        hitboxes = src('src/server/combat/EntityHitboxService.luau')
        self.assertIn('CollectionService:GetTagged("Game1CombatHitbox")', overlay)
        self.assertNotIn('for _, descendant in ipairs(Workspace:GetDescendants())', overlay)
        self.assertIn('nextHitboxRenderAt = now + 1 / 8', overlay)
        preview = src('src/client/dev/MeleeArcPreview.luau')
        self.assertIn('MeleeArcPreview.new()', overlay)
        self.assertIn('MeleeArcDebugAnchor', preview)
        self.assertNotIn('Workspace:Raycast', preview)
        self.assertIn('RenderStepped:Connect', preview)  # camera guide only
        self.assertIn('hitboxConnection:Disconnect()', overlay)
        self.assertIn('ringPreview:Destroy()', overlay)
        self.assertIn('CollectionService:AddTag(entity, "Game1CombatHitbox")', hitboxes)
        self.assertIn('CollectionService:RemoveTag(entity, "Game1CombatHitbox")', hitboxes)
        self.assertIn('task.delay(math.max(0, hitEndEvent.time - lead)', client)
        self.assertIn('MELEE_AIM_SEND_INTERVAL = 0.10', client)
        self.assertIn('now <= meleeHitEndAt and now >= nextMeleeAimAt', client)
        self.assertEqual(client.count('publishMeleeAim()'), 3)  # definition, bounded refresh, late capture


if __name__ == '__main__':
    unittest.main()
