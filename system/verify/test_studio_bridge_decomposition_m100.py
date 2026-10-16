"""M100: Studio bridge composition root, module boundaries and packaging contracts."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "system/studio-plugin"
MAIN = (PLUGIN / "Game1Bridge.server.luau").read_text(encoding="utf-8")
PROJECT = json.loads((PLUGIN / "plugin.project.json").read_text(encoding="utf-8"))
MODULES = {
    name: (PLUGIN / "modules" / f"{name}.luau").read_text(encoding="utf-8")
    for name in ("StudioModelLoadCommands", "StudioActorSpawnCommands", "StudioDebugPreferenceBridge")
}

class StudioBridgeDecompositionM100(unittest.TestCase):
    def test_three_standalone_modules_are_explicitly_packaged(self):
        for name, source in MODULES.items():
            with self.subTest(name=name):
                self.assertEqual(PROJECT["tree"]["modules"][name]["$path"], f"modules/{name}.luau")
                self.assertIn(f"require(script.Parent.modules.{name})", MAIN)
                self.assertIn("return function(services)", source)

    def test_main_is_only_a_composition_root_for_extracted_commands(self):
        self.assertLess(len(MAIN.splitlines()), 950)
        self.assertNotIn("local function handleModelLoad(", MAIN)
        self.assertNotIn("local function handleMonsterSpawn(", MAIN)
        self.assertNotIn("local function readStudioDebugPreferences(", MAIN)
        self.assertIn("local handleModelLoad = StudioModelLoadCommands({", MAIN)
        self.assertIn("local handleMonsterSpawn = StudioActorSpawnCommands({", MAIN)
        self.assertIn("StudioDebugPreferenceBridge({", MAIN)

    def test_commands_still_dispatch_with_original_names_and_edit_mode_gate(self):
        for signature in (
            'data.command == "model-load"', 'handleModelLoad(data)',
            'data.command == "monster-spawn"', 'handleMonsterSpawn(data)',
            'data.command == "timeline-editor"', 'handleTimelineEditor(data)',
            'data.command == "location-authoring"', 'locationCommands.handle(data)',
            'if RunService:IsRunning() then', 'task.wait(1)',
        ):
            with self.subTest(signature=signature):
                self.assertIn(signature, MAIN)
        self.assertLess(MAIN.index('local handleMonsterSpawn = '), MAIN.index('local function pollBridge()'))

    def test_model_rig_guards_and_original_result_protocol_are_preserved(self):
        source = MODULES['StudioModelLoadCommands']
        for token in (
            'validSegment(raw)', 'Game1CharacterRig', 'Game1MonsterRig',
            'Game1NpcRig', 'Game1WeaponTemplate', 'assertExpectedBones(importedRig, metadata.expectedBones)',
            'AssetService:LoadAssetAsync(assetId)', 'CharacterTemplate.EnsureCanonicalRoot',
            '"/model-load-result"', 'pcall(postModelLoadResult, result)',
            'return handleModelLoad',
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)
        self.assertIn('require(script.Parent.CharacterTemplate)', source)
        self.assertNotIn('script.Parent.modules.CharacterTemplate', source)

    def test_actor_markers_preserve_npc_preview_and_atomic_result(self):
        source = MODULES['StudioActorSpawnCommands']
        for token in (
            'require(script.Parent.NpcSpawnPreview)', 'require(script.Parent.NpcSpawnPlacement)',
            'NpcSpawnPreview.Attach(', 'NpcSpawnPlacement.Place(',
            'Game1MonsterSpawnMarker', 'Game1NpcSpawnMarker',
            '"place"', '"upsert"', '"select"', '"delete"', '"sync"',
            '"/monster-spawn-result"', 'pcall(postMonsterSpawnResult, result)',
            'return handleMonsterSpawn',
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)

    def test_debug_settings_preserve_roundtrip_and_run_state_wiring(self):
        source = MODULES['StudioDebugPreferenceBridge']
        for token in (
            'Game1StudioDebugPreferences_v1', 'Game1StudioPreferences',
            'plugin:GetSetting(', 'plugin:SetSetting(',
            'LastLoadoutArchetype', 'LastLoadoutWeaponSlug',
            'ClientPreferencesReady', 'ReplicatedStorage.ChildAdded:Connect(',
            'RunService:GetPropertyChangedSignal("RunState")',
            'disconnectStudioPreferenceBridge()',
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)

    def test_installer_requires_new_modules_in_rojo_output(self):
        installer = (PLUGIN / 'install.ps1').read_text(encoding='utf-8')
        for name in MODULES:
            self.assertIn(f"'{name}'", installer)
        self.assertIn('Get-FileHash $Installed -Algorithm SHA256', installer)
        self.assertIn("'model bridge v24'", installer)

    def test_timeline_and_deco_remain_owned_by_existing_modules(self):
        self.assertIn('local function handleTimelineEditor(data: any)', MAIN)
        self.assertIn('local decoManager = DecoManager.new({', MAIN)
        self.assertIn('StudioMarkerVisibility.new(plugin, toolbar, Workspace)', MAIN)

if __name__ == '__main__':
    unittest.main()
