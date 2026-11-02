"""M192: isolated character assembly bench: contract, ownership and security tests.

Static checks cannot replace a Studio Edit/Play regression, but catch packaging,
asset publication regressions, accidental gameplay integration and missing guards.
"""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / 'system/studio-plugin'
MODULES = PLUGIN / 'modules'
SHARED = ROOT / 'src/shared/character'
TESTBED = ROOT / 'src/server/testbed'


def source(path):
    return path.read_text(encoding='utf-8-sig')


class CharacterTestStandM192(unittest.TestCase):
    def test_plugin_bundle_has_all_modules_and_toolbar(self):
        manifest = json.loads(source(PLUGIN / 'plugin.project.json'))
        for name in ('StudioCharacterTestStand', 'StudioCharacterStandBuilder',
                     'StudioCharacterStandPlacement', 'StudioCharacterStandWidget'):
            self.assertEqual(manifest['tree']['modules'][name]['$path'], f'modules/{name}.luau')
            self.assertTrue((MODULES / f'{name}.luau').is_file())
        main = source(PLUGIN / 'Game1Bridge.server.luau')
        self.assertIn('StudioCharacterTestStand.new({', main)
        self.assertIn('local toolbar = plugin:CreateToolbar("game1")', main)
        self.assertIn('Game1CharacterStand', source(MODULES / 'StudioCharacterTestStand.luau'))
        self.assertIn('StudioCharacterTestStand', source(PLUGIN / 'install.ps1'))

    def test_builder_uses_runtime_builder_without_reimplementing_binds(self):
        s = source(MODULES / 'StudioCharacterStandBuilder.luau')
        runtime = source(ROOT / 'src/server/character/CharacterAssemblyBuilder.luau')
        self.assertIn('CharacterAssemblyBuilder', s)
        self.assertIn('game:GetService("ServerScriptService"):GetChildren()', s)
        self.assertIn('candidate.Name == "Game1Server" and candidate:IsA("Script")', s)
        self.assertNotIn('FindFirstChild("Game1Server")', s)
        self.assertIn('assemblyBuilder.Build(row.assembly', s)
        self.assertIn('AssetService', source(MODULES / 'StudioCharacterTestStand.luau'))
        self.assertIn('loadPublished(assetService, id)', s)
        self.assertIn('CharacterAtlasBinder.Apply', runtime)
        self.assertNotIn('mesh.CFrame = target.WorldCFrame', s)
        self.assertNotIn('OpenCloud', s)

    def test_stand_is_isolated_in_workspace_without_remotes_or_players(self):
        placement = source(MODULES / 'StudioCharacterStandPlacement.luau')
        self.assertIn('Game1CharacterTestStands', placement)
        self.assertIn('draft:Clone()', placement)
        self.assertIn('GetBoundingBox()', placement)
        self.assertIn('Game1CharacterTestStandPrompt', placement)
        self.assertIn('Enum.KeyCode.E', placement)
        self.assertIn('clone:PivotTo(CFrame.new(delta) * current)', placement)
        for forbidden in ('Players', 'RemoteEvent', 'UpdateAsync', 'Publish', 'PivotTo(CFrame.Angles'):
            self.assertNotIn(forbidden, placement)

    def test_catalog_is_deterministic_and_ignores_unpublished_procedural(self):
        catalog = source(SHARED / 'CharacterStandAnimationCatalog.luau')
        self.assertIn('table.sort(entries', catalog)
        self.assertIn('animationId:match(', catalog)
        self.assertIn('clip.animationId', catalog)
        self.assertIn('profile.weapons', catalog)
        self.assertIn('for _, scope in {"base", "emotions"}', catalog)
        self.assertIn('profile[scope]', catalog)
        self.assertNotIn('LoadAnimation', catalog)

    def test_studio_guard_and_one_track_at_a_time(self):
        script = source(TESTBED / 'CharacterTestStand.server.luau')
        playback = source(TESTBED / 'CharacterTestStandPlayback.luau')
        self.assertRegex(script, r'if not RunService:IsStudio\(\) then return end')
        self.assertIn('Workspace.ChildAdded:Connect(bindFolder)', script)
        self.assertIn('folder.ChildAdded:Connect(attach)', script)
        self.assertIn('prompt.Triggered:Connect', playback)
        self.assertIn('index = index % #clips + 1', playback)
        self.assertIn('clearTrack()', playback)
        self.assertIn('connection:Disconnect()', playback)
        self.assertIn('Game1SkeletonSignature', playback)
        for forbidden in ('DataStoreService', 'Players.PlayerAdded', 'RemoteEvent', 'Humanoid:LoadAnimation'):
            self.assertNotIn(forbidden, playback)

    def test_undo_and_draft_cleanup(self):
        main = source(MODULES / 'StudioCharacterTestStand.luau')
        self.assertIn('TryBeginRecording', main)
        self.assertIn('FinishRecording', main)
        self.assertIn('self.draft:Destroy()', main)
        self.assertIn('services.plugin.Unloading:Connect', main)
        self.assertIn('self.runService:IsRunning()', main)
        self.assertIn('FilterDescendantsInstances', main)


if __name__ == '__main__':
    unittest.main()
