"""M95: Studio markers, publication descriptions and spawn defaults."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def read(path):
    return (ROOT / path).read_text(encoding="utf-8")

class M95Contracts(unittest.TestCase):
    def test_04_plugin_toggle_only_affects_marker_visuals(self):
        module = read("system/studio-plugin/modules/StudioMarkerVisibility.luau")
        main = read("system/studio-plugin/Game1Bridge.server.luau")
        project = json.loads(read("system/studio-plugin/plugin.project.json"))
        for name in ("Game1MonsterSpawnMarker", "Game1NpcSpawnMarker", "Game1LocationMarker"):
            self.assertIn(name, module)
        for item in ("LocalTransparencyModifier", '"Enabled", false', 'workspace.DescendantAdded:Connect',
                     'plugin:SetSetting(SETTING_KEY, value)', 'self.button:SetActive(value)'):
            self.assertIn(item, module)
        self.assertIn("StudioMarkerVisibility.new(plugin, toolbar, Workspace)", main)
        self.assertIn("StudioMarkerVisibility", project['tree']['modules'])
        self.assertNotIn('Destroy()', module.split('function Visibility:SetVisible', 1)[1].split('function Visibility:Destroy', 1)[0])

    def test_05_publication_text_policy_is_contextual_for_models(self):
        js = read("system/control-center/static/publication-descriptions.js")
        html = read("system/control-center/static/index.html")
        self.assertIn('`${base} ${label}`', js)
        self.assertIn('publication-descriptions.js?v=1', html)
        for page in ('deco-assets', 'monster-assets', 'npc-assets', 'weapon-assets', 'character-assets'):
            self.assertIn('game1SyncPublicationDescription(', read('system/control-center/static/'+page+'.js'))
        self.assertIn('Game1 Location Asset Oak Tree', html)

    def test_05b_animation_publication_sync_stays_inside_function(self):
        for kind in ("monster", "npc"):
            js = read(f"system/control-center/static/{kind}-assets.js")
            start = js.index(f"function {kind}RenderAnimationTarget()")
            end = js.index(f"async function {kind}SelectAnimationTarget(")
            function_body = js[start:end]
            self.assertIn(f'game1SyncPublicationDescription("{kind}-animation-publication-description"', function_body)
            self.assertIn('rows.find(row=>row.slug===select.value)', function_body)
            self.assertNotIn('};const current=rows.find(', function_body)
            self.assertTrue(function_body.strip().endswith('}'))

    def test_06_monster_population_keeps_defaults_npc_is_fixed(self):
        backend = read('system/control-center/monster_spawn_store.py')
        self.assertIn('"spawnRadius": 15, "maxAlive": 3', backend)
        html = read('system/control-center/static/index.html')
        monster_js = read('system/control-center/static/monster-spawns.js')
        npc_js = read('system/control-center/static/npc-spawns.js')
        for suffix in ('radius', 'max-alive'):
            self.assertIn(f'id="monster-spawn-{suffix}"', html)
            self.assertNotIn(f'id="npc-spawn-{suffix}"', html)
            self.assertIn(f"$('monster-spawn-{suffix}')", monster_js)
            self.assertNotIn(f"$('npc-spawn-{suffix}')", npc_js)
        self.assertIn('if self.kind == "npc"', backend)
        self.assertIn('else {"mapKey": "main", "respawnSeconds": 10, "spawnRadius": 15, "maxAlive": 3}', backend)


if __name__ == "__main__":
    unittest.main()
