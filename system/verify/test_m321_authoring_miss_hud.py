"""M321: authoring isolation, authoritative attack outcome, and health UI."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]

def source(path):
    return (ROOT / path).read_text(encoding="utf-8")


def miss_outcome(committed, total_damage, alive, pursued=False, aimed_near=False):
    """M323: zero damage alone is not enough for an on-screen Miss."""
    return int(committed and total_damage <= 0 and alive and (pursued or aimed_near))


class RuntimeAuthoringTests(unittest.TestCase):
    def test_authoring_markers_removed_from_running_world_but_not_editor(self):
        cleanup = source('src/server/world/Game1AuthoringCleanupService.luau')
        catalog = source('src/server/bootstrap/ServiceCatalog.luau')
        self.assertIn('Workspace.ChildAdded:Connect(removeAuthoringRoot)', cleanup)
        self.assertIn('Workspace:FindFirstChild("Game1Authoring")', cleanup)
        self.assertIn('instance:Destroy()', cleanup)
        self.assertLess(catalog.index('name = "Game1AuthoringCleanupService"'),
                        catalog.index('name = "MonsterSpawnerService"'))
        self.assertNotIn('removeAuthoringVisualsFromSimulation', source('src/server/monster/MonsterSpawnerService.luau'))
        self.assertNotIn('markers:Destroy()', source('src/server/npc/NpcSpawnerService.luau'))
        self.assertIn('plugin:GetSetting(SETTING_KEY)', source('system/studio-plugin/modules/StudioMarkerVisibility.luau'))
        self.assertNotIn('StudioPlugin', cleanup)


class MissTests(unittest.TestCase):
    def test_one_miss_for_zero_outcome_and_no_miss_for_positive_damage(self):
        self.assertEqual(miss_outcome(True, 0, True), 0)
        self.assertEqual(miss_outcome(True, 0, True, pursued=True), 1)
        self.assertEqual(miss_outcome(True, 0, True, aimed_near=True), 1)
        self.assertEqual(miss_outcome(True, 0, False, pursued=True), 0)
        self.assertEqual(miss_outcome(False, 0, True, aimed_near=True), 0)
        self.assertEqual(miss_outcome(True, 10, True, aimed_near=True), 0)
        session = source('src/server/combat/AttackSessionStore.luau')
        attack = source('src/server/combat/AttackService.luau')
        resolver = source('src/server/combat/AttackDamageResolver.luau')
        self.assertIn('damageDealt = false', session)
        self.assertIn('function AttackSessionStore.MarkDamage(', session)
        self.assertIn('if finalDamage > 0 then damagedTargets += 1 end', resolver)
        self.assertIn('if damagedTargets > 0 then', attack)
        self.assertIn('if reportMiss and not finished.damageDealt', attack)
        self.assertIn('AttackSessionStore.Finish(player, character, serial, clientAttackId)', attack)
        self.assertIn('CombatFeedbackService.PublishAttackOutcome(character, aimedState, false)', attack)
        self.assertIn('clearAttackStateLater(player, character, serial, clientAttackId, attackDuration, not isBow)', attack)

    def test_bow_fires_on_release_not_on_capture_and_respects_zero_damage(self):
        bow = source('src/server/combat/BowHitscanService.luau')
        attack = source('src/server/combat/AttackService.luau')
        self.assertEqual(bow.count('DamageService.Apply('), 1)
        self.assertIn('return true, damageDealt', bow)
        self.assertIn('local released, damageDealt = BowHitscanService.Release(', attack)
        self.assertIn('if released and damageDealt <= 0', attack)
        self.assertNotIn('CombatFeedbackService.PublishMissOverPlayer', source('src/server/combat/BowHitscanService.luau'))

    def test_monster_and_npc_misses_are_sent_to_victim_only(self):
        service = source('src/server/combat/CombatFeedbackService.luau')
        client = source('src/client/combat/CombatFeedbackController.luau')
        monster = source('src/server/monster/MonsterAttackExecutor.luau')
        npc = source('src/server/npc/NpcCombatAIService.luau')
        self.assertIn('Players:GetPlayerFromCharacter(character)', service)
        self.assertIn('remote:FireClient(player, {', service)
        self.assertIn('publishLabel(character, "miss")', service)
        self.assertIn('CombatFloatingText.ShowMiss(payload.target, payload.position)', client)
        self.assertIn('function CombatFloatingText.ShowMiss', source('src/client/combat/CombatFloatingText.luau'))
        for text in (monster, npc):
            self.assertIn('CombatFeedbackService.PublishMissOverPlayer(target)', text)
            self.assertIn('"Miss"', text)


class HealthUiTests(unittest.TestCase):
    def test_reference_layout_and_authoritative_HP(self):
        init = source('src/client/init.client.luau')
        hud = source('src/client/combat/PlayerHealthHudController.luau')
        view = source('src/client/combat/HealthBarView.luau')
        visibility = source('src/client/combat/OverheadHealthController.luau')
        self.assertIn('PlayerHealthHudController.Start()', init)
        self.assertIn('string.format("%d / %d"', hud)
        self.assertIn('healthColor', view)
        self.assertIn('profile.colors', hud)
        self.assertIn('Instance.new("UICorner")', hud)
        self.assertIn('TweenService:Create(fill', hud)
        self.assertNotIn('AttackSpeed', hud)
        self.assertIn('visualTopOffset(model, anchor)', view)
        self.assertIn('MonsterSlug', view)
        self.assertIn('model:GetAttribute("Level")', view)
        self.assertIn('TweenService:Create(fill, TWEEN, goal)', view)
        self.assertIn('model:GetAttribute("MonsterTargetUserId") == player.UserId', visibility)
        self.assertIn('model == aimedMonster', visibility)
        self.assertNotIn('SetAttribute("HP"', view)
        self.assertNotIn('SetAttribute("HP"', hud)
        self.assertIn('tonumber(stats.Level)', source('src/server/monster/MonsterInitialAttributes.luau'))

if __name__ == '__main__':
    unittest.main()
