"""M362: overhead lifecycle contracts + scenario transitions.

No headless Python test can drive Roblox replication or Workspace:Raycast.
The scenario matrix below checks the *authored* UI visibility policy while the
source checks protect the actual Roblox listener/rebind contracts.
Studio Play confirmation is still required for engine/replication behaviour.
"""
from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def code(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def visible(*, state: str = "Alive", distance: float = 12, radius: float = 100,
            aimed: bool = False, locked: bool = False, combat: bool = False,
            target_user: int = 0, user: int = 10, preview_all: bool = False) -> bool:
    """Python contract mirror, *not* execution of the Luau client."""
    return (state == "Alive" and distance <= radius and
            (preview_all or aimed or locked or (combat and target_user == user)))


class ClientLifecycleContracts(unittest.TestCase):
    def setUp(self):
        self.controller = code("src/client/combat/MnpcOverheadController.luau")
        self.registry = code("src/client/combat/MnpcOverheadRegistry.luau")
        self.policy = code("src/client/combat/OverheadVisibilityPolicy.luau")
        self.pool = code("src/client/combat/OverheadViewPool.luau")
        self.view = code("src/client/combat/HealthBarView.luau")

    def test_new_monster_bound_after_root_and_attributes_replicate_in_any_order(self):
        for fragment in ('folder.ChildAdded:Connect', 'model.ChildAdded:Connect(refresh)',
                         'model.AttributeChanged:Connect', 'Game1MonsterRuntime', 'LifeState',
                         'MonsterSlug', 'model:FindFirstChild("RootCollider")'):
            self.assertIn(fragment, self.registry)
        self.assertNotIn('WaitForChild("RootCollider", 5)', self.registry)

    def test_initially_missing_gui_retries_without_per_monster_player_listeners(self):
        self.assertEqual(self.controller.count('player.ChildAdded:Connect('), 1)
        self.assertIn('if child:IsA("PlayerGui") then syncGui() end', self.controller)
        self.assertIn('if not currentGui then return end', self.controller)
        self.assertNotIn('player:WaitForChild("PlayerGui")', self.controller)

    def test_gui_replacement_rebuilds_views_for_living_monsters(self):
        self.assertIn('player.ChildRemoved:Connect', self.controller)
        self.assertIn('if currentGui ~= gui then', self.controller)
        self.assertIn('pool:Clear()', self.controller)
        self.assertIn('gui.Parent == expectedParent', self.view)
        self.assertIn('gui.Adornee == anchor and anchor.Parent == model', self.view)

    def test_lost_billboard_self_heals_without_mutating_registry_mid_iteration(self):
        self.assertIn('if view and not view.IsAttached(currentGui) then', self.controller)
        self.assertIn('pool:Release(model, now, true)', self.controller)
        self.assertIn('table.insert(pending', self.controller)
        self.assertIn('for _, request in ipairs(pending)', self.controller)

    def test_streamed_out_root_rebinds_after_stream_in(self):
        self.assertIn('model.ChildRemoved:Connect(refresh)', self.registry)
        self.assertIn('child == record.anchor', self.registry)
        self.assertIn('self.changed(model)', self.registry)
        self.assertIn('task.defer(refresh)', self.registry)

    def test_old_monster_deleted_and_new_respawn_watched(self):
        self.assertIn('folder.ChildRemoved:Connect', self.registry)
        self.assertIn('self:_remove(model)', self.registry)
        spawner = code("src/server/monster/MonsterSpawnerService.luau")
        population = code("src/server/monster/MonsterPopulationController.luau")
        self.assertIn('MnpcLifecycle.Publish(model, navigationRoot, ensureMonstersFolder())', spawner)
        self.assertIn('population:ScheduleRespawn(state, entry.diedAt)', spawner)
        self.assertIn('spawnReserved(state)', population)

    def test_spawning_visual_fade_recalculates_overhead_offset(self):
        presentation = code("src/server/monster/MonsterSpawnPresentation.luau")
        self.assertIn('model:SetAttribute("MonsterSpawning", true)', presentation)
        self.assertIn('model:SetAttribute("MonsterSpawning", false)', presentation)
        self.assertIn('model:GetAttributeChangedSignal("MonsterSpawning")', self.view)
        self.assertIn('view.RefreshVisualOffset()', self.view)
        self.assertIn('baseOffset = visualTopOffset(model, anchor)', self.view)

    def test_server_owns_life_and_target_state(self):
        initial = code("src/server/monster/MonsterInitialAttributes.luau")
        combat = code("src/server/monster/MonsterCombatState.luau")
        self.assertIn('model:SetAttribute("LifeState", "Alive")', initial)
        self.assertIn('agent.model:SetAttribute("MonsterTargetUserId", 0)', combat)
        self.assertIn('model:GetAttribute("MonsterCombatActive") == true', self.policy)
        self.assertIn('model:GetAttribute("MonsterTargetUserId") == context.userId', self.policy)
        self.assertIn('model:GetAttribute("LifeState") == "Alive"', self.registry)

    def test_reticle_updates_without_sticky_target_and_never_checks_without_monsters(self):
        self.assertIn('aimed = if playerRoot and next(registry.readyMonsters) ~= nil then reticleTarget(radius) else nil', self.controller)
        self.assertIn('CameraController.GetAimRay()', self.controller)
        self.assertIn('Workspace:Raycast(origin, direction * (radius + AIM_CAMERA_MARGIN_STUDS), reticleParams)', self.controller)
        self.assertEqual(self.controller.count('RaycastParams.new()'), 1)
        self.assertNotIn('AIM_MAX_DISTANCE = 420', self.controller)
        self.assertIn('AIM_CAMERA_MARGIN_STUDS = 64', self.controller)
        self.assertIn('reticleParams.FilterDescendantsInstances = if character then {character} else {}', self.controller)

    def test_radius_and_mobile_focus_are_independent_of_combat(self):
        self.assertIn('distSq = delta:Dot(delta)', self.controller)
        self.assertIn('CameraController.AutoAimTarget()', self.controller)
        self.assertIn('context.showAll or focused or attackingUs', self.policy)

    def test_idle_frame_does_not_rewrite_the_same_gui_properties(self):
        self.assertNotIn('if showNameRequested == showName and showHpRequested == showHP then return end', self.view)
        self.assertIn('showNameRequested = showName', self.view)
        self.assertIn('if gui.Enabled ~= enabled then gui.Enabled = enabled end', self.view)
        self.assertIn('if plate.Visible ~= visibleHP then plate.Visible = visibleHP end', self.view)

    def test_model_and_view_cleanup_disconnect_subscriptions(self):
        self.assertIn('connection:Disconnect()', self.registry)
        self.assertIn('for _, connection in ipairs(connections) do connection:Disconnect() end', self.view)
        self.assertIn('gui:Destroy()', self.view)
        self.assertIn('view.Unbind', self.pool)
        self.assertIn('generation == token', self.view)


class VisibilityScenarioMatrix(unittest.TestCase):
    def test_14_lifecycle_scenarios(self):
        scenarios = (
            ('first_spawn_aimed', dict(aimed=True), True),
            ('focused_before_visual_reveal', dict(aimed=True), True),
            ('neutral_not_aimed', {}, False),
            ('chasing_our_player', dict(combat=True, target_user=10), True),
            ('attacking_another_player', dict(combat=True, target_user=99), False),
            ('returning_while_still_aimed', dict(combat=True, target_user=0, aimed=True), True),
            ('returning_without_focus', dict(combat=True, target_user=0), False),
            ('home_idle_and_focused', dict(aimed=True), True),
            ('dying_while_returning', dict(state='Dying', aimed=True), False),
            ('death_idle_while_aimed', dict(state='DeathIdle', aimed=True), False),
            ('respawn_new_instance_aimed', dict(aimed=True), True),
            ('mobile_locked_target', dict(locked=True), True),
            ('out_of_radius_while_aimed', dict(distance=101, aimed=True), False),
            ('studio_show_all', dict(preview_all=True), True),
        )
        for name, inputs, expected in scenarios:
            with self.subTest(name=name):
                self.assertEqual(visible(**inputs), expected)

    def test_repeat_kill_respawn_with_return_and_retarget(self):
        sequence = [
            (dict(aimed=True), True),
            (dict(combat=True, target_user=10), True),
            (dict(combat=True, target_user=0, aimed=True), True),
            (dict(state='Dying', aimed=True), False),
            (dict(state='DeathIdle', aimed=True), False),
            (dict(aimed=True), True),
            (dict(combat=True, target_user=10), True),
            (dict(state='Dying', aimed=True), False),
            (dict(aimed=True), True),
        ]
        for data, expected in sequence:
            self.assertEqual(visible(**data), expected)


if __name__ == '__main__':
    unittest.main()
