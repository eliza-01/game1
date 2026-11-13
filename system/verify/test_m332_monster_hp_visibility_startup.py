"""M332 regression: no cached aggro, explicit debug all and spawn resilience."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def source(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def should_show(alive, in_range, aimed, locked, active, target_user, me, preview_all=False):
    return alive and in_range and (preview_all or aimed or locked or (active and target_user == me))

class MonsterHealthVisibilityTests(unittest.TestCase):
    def test_policy_is_per_target_and_current_not_persistent(self):
        me = 123
        self.assertFalse(should_show(True, True, False, False, False, 0, me))
        self.assertTrue(should_show(True, True, True, False, False, 0, me))
        self.assertTrue(should_show(True, True, False, True, False, 0, me))
        self.assertTrue(should_show(True, True, False, False, True, me, me))
        self.assertFalse(should_show(True, True, False, False, True, 999, me))
        self.assertFalse(should_show(True, True, False, False, False, me, me))
        self.assertFalse(should_show(True, False, True, False, True, me, me))
        self.assertFalse(should_show(False, True, True, False, True, me, me))
        self.assertTrue(should_show(True, True, False, False, False, 0, me, True))

    def test_no_spawn_timeout_and_subscriptions_removed(self):
        over = source('src/client/combat/OverheadHealthController.luau')
        self.assertNotIn('WaitForChild("RootCollider", 5)', over)
        self.assertIn('monster.ChildAdded:Connect', over)
        self.assertIn('monster:GetAttributeChangedSignal(attribute):Connect(attachWhenReady)', over)
        for key in ('Game1MonsterRuntime', 'MonsterSlug', 'LifeState'):
            self.assertIn('"' + key + '"', over)
        self.assertIn('clearPendingMonster(monster)', over)
        self.assertIn('for model in pairs(pendingMonsters) do clearPendingMonster(model) end', over)
        self.assertIn('monster.Parent ~= watchedFolder', over)
        self.assertIn('monster:FindFirstChild("RootCollider")', over)
        self.assertIn('monster.ChildRemoved:Connect', over)
        self.assertIn('if child == anchor then', over)
        self.assertIn('anchorRemovedConnections[model]', over)

    def test_aggression_is_live_only_and_default_hidden(self):
        over = source('src/client/combat/OverheadHealthController.luau')
        view = source('src/client/combat/HealthBarView.luau')
        self.assertIn('model:GetAttribute("MonsterCombatActive") == true', over)
        self.assertIn('model:GetAttribute("MonsterTargetUserId") == player.UserId', over)
        self.assertIn('HealthUiSettings.ShowAllMonsters() or focused or attackingUs', over)
        self.assertIn('view.SetVisible(alive and inRange', over)
        self.assertIn('gui.Enabled = false', view)
        self.assertIn('if monster then', view)
        self.assertIn('ratio <= 0.30', view)
        self.assertIn('ratio <= 0.65', view)
        state = source('src/server/monster/MonsterCombatState.luau')
        self.assertIn('agent.model:SetAttribute("MonsterTargetUserId", 0)', state)
        self.assertIn('agent.model:SetAttribute("MonsterCombatActive", false)', state)

    def test_studio_all_hp_is_explicit_and_reset(self):
        settings = source('src/client/combat/HealthUiSettings.luau')
        ui = source('src/client/dev/HealthUiDebugController.luau')
        self.assertIn('local previewAllMonsters = false', settings)
        self.assertIn('return preview ~= nil and previewAllMonsters', settings)
        self.assertIn('previewAllMonsters = false', settings.split('function Settings.ClearPreview()', 1)[1])
        self.assertIn('All HP: OFF', ui)
        self.assertIn('Settings.SetShowAllMonsters(enabled)', ui)
        self.assertIn('Settings.ClearPreview()', ui)
        self.assertIn('else stopPreview() end', ui)
        self.assertIn('close.Activated:Connect(function()', ui)

if __name__ == '__main__':
    unittest.main()
