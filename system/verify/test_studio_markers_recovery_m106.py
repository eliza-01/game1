"""M106: Studio marker visibility must survive plugin reload and Play/Edit transitions."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MARKERS = (ROOT / "system/studio-plugin/modules/StudioMarkerVisibility.luau").read_text(encoding="utf-8")
ACTOR_MARKERS = (ROOT / "system/studio-plugin/modules/StudioActorSpawnCommands.luau").read_text(encoding="utf-8")
LOCATION_MARKERS = (ROOT / "system/studio-plugin/modules/LocationCommands.luau").read_text(encoding="utf-8")


class MarkerVisibilityRecoveryM106(unittest.TestCase):
    def test_show_normalizes_originally_hidden_parts_after_restart(self):
        # When the old plugin persisted a hidden override, its transient
        # self.original table is gone after restart. Show must have a fallback.
        self.assertIn('return "LocalTransparencyModifier", 1, 0', MARKERS)
        self.assertIn('return "Enabled", false, true', MARKERS)
        self.assertIn('return "Visible", false, true', MARKERS)
        self.assertIn('local value = if record then record.value else defaultVisible', MARKERS)
        self.assertIn('if old == hiddenValue then defaultVisible else old', MARKERS)

    def test_toggle_persists_preference_but_unloading_restores_visuals(self):
        self.assertIn('plugin:GetSetting(SETTING_KEY)', MARKERS)
        self.assertIn('plugin:SetSetting(SETTING_KEY, value)', MARKERS)
        self.assertIn('plugin.Unloading:Connect', MARKERS)
        destroy = MARKERS.split('function Visibility:Destroy()', 1)[1]
        self.assertIn('self.visible = true', destroy)
        self.assertIn('self:_apply(self.workspace)', destroy)
        self.assertNotIn('self:SetVisible(true)', destroy)
        self.assertIn('if self.destroyed then return end', destroy)

    def test_toggle_reports_when_no_marker_models_are_loaded(self):
        self.assertIn('[game1][studio-markers] %s · %d marker(s)', MARKERS)
        self.assertIn('count == 0', MARKERS)
        self.assertIn('Restore markers in Asset Manager', MARKERS)
        self.assertIn('Game1MonsterSpawnMarker', MARKERS)
        self.assertIn('Game1NpcSpawnMarker', MARKERS)
        self.assertIn('Game1LocationMarker', MARKERS)

    def test_plugin_owns_marker_defaults_and_runtime_owns_play_cleanup(self):
        self.assertIn('marker:SetAttribute(if kind == "npc"', ACTOR_MARKERS)
        self.assertIn('marker:SetAttribute("Game1LocationMarker", true)', LOCATION_MARKERS)
        self.assertIn('part.Transparency = transparency', ACTOR_MARKERS)
        self.assertIn('item.Transparency = transparency', LOCATION_MARKERS)
        self.assertNotIn('Transparency = if self.visible', MARKERS)
        self.assertNotIn('marker:Destroy()', MARKERS)


if __name__ == '__main__':
    unittest.main()
