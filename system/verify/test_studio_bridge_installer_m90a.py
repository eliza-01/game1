"""Contract checks for the built Studio bridge and the installer marker policy."""
from pathlib import Path
import re
import json
import unittest


ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "system/studio-plugin/Game1Bridge.server.luau"
INSTALLER = ROOT / "system/studio-plugin/install.ps1"


class StudioBridgeInstallerContract(unittest.TestCase):
    def test_all_installer_required_markers_exist_in_plugin_source(self):
        # The Rojo bundle also contains modules listed in plugin.project.json.
        project = json.loads((PLUGIN.parent / "plugin.project.json").read_text(encoding="utf-8"))
        def bundled_paths(node):
            if isinstance(node, dict):
                if "$path" in node:
                    yield PLUGIN.parent / node["$path"]
                else:
                    for child in node.values():
                        yield from bundled_paths(child)
        source = "\n".join(path.read_text(encoding="utf-8") for path in bundled_paths(project["tree"]))
        installer = INSTALLER.read_text(encoding="utf-8")
        match = re.search(r"foreach\(\$Marker in @\((.*?)\)\)\s*\{", installer, re.S)
        self.assertIsNotNone(match, "Installer required-marker check missing")
        markers = re.findall(r"'([^']+)'", match.group(1))
        self.assertGreaterEqual(len(markers), 10)
        for marker in markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, source)
        self.assertNotIn("Game1ControlCenter", markers)

    def test_removed_toolbar_button_is_rejected_and_legacy_check_is_preserved(self):
        source = PLUGIN.read_text(encoding="utf-8")
        installer = INSTALLER.read_text(encoding="utf-8")
        forbidden = re.search(r"foreach\(\$RemovedMarker in @\((.*?)\)\)\s*\{", installer, re.S)
        self.assertIsNotNone(forbidden)
        self.assertIn("'Game1ControlCenter'", forbidden.group(1))
        self.assertNotIn('"Game1ControlCenter"', source)
        self.assertIn("local function checkAgent()", source)

    def test_monster_spawn_command_is_routed_in_edit_mode(self):
        source = PLUGIN.read_text(encoding="utf-8")
        self.assertIn('elseif data.command == "monster-spawn" then', source)
        self.assertIn('handleMonsterSpawn(data)', source)
        self.assertIn('local function handleMonsterSpawn(', (PLUGIN.parent / 'modules/StudioActorSpawnCommands.luau').read_text(encoding='utf-8'))
        self.assertIn('if RunService:IsRunning() then', source)


if __name__ == "__main__":
    unittest.main()
