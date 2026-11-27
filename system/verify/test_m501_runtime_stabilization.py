"""M501 tests: synthetic real XML script freshness and client boundary checks."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services.runtime_script_freshness import expected_scripts, verify_scripts
from services.location_runtime_build import RuntimePlaceBuilder, _parse
from test_location_runtime_build import fixture


def read(path):
    return (ROOT / path).read_text(encoding='utf8')


def item(parent, name, cls, source=None):
    node = ET.SubElement(parent, 'Item', {'class': cls, 'referent': 'RBX_' + name})
    props = ET.SubElement(node, 'Properties')
    ET.SubElement(props, 'string', name='Name').text = name
    if source is not None:
        ET.SubElement(props, 'ProtectedString', name='Source').text = source
    return node


class RuntimeScripts(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source, self.rows = fixture(self.root)
        self.tree = ET.parse(self.source)
        project = {'tree': {'$className': 'DataModel', 'ReplicatedStorage': {'Game1Shared': {'$path': 'src/shared'}},
                            'StarterPlayer': {'StarterPlayerScripts': {'Game1Client': {'$path': 'src/client'}}},
                            'ServerScriptService': {'Game1Server': {'$path': 'src/server'}}}}
        (self.root / 'default.project.json').write_text(json.dumps(project))
        for path, source in [('src/shared/UI.luau', 'return {}\n'),
                             ('src/client/init.client.luau', 'print("client")\n'),
                             ('src/client/character/Creation.luau', 'return 1\n'),
                             ('src/server/init.server.luau', 'print("server")\n')]:
            file = self.root / path
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(source)
        storage = self.tree.getroot().find('./Item[@class="ReplicatedStorage"]')
        shared = item(storage, 'Game1Shared', 'Folder')
        item(shared, 'UI', 'ModuleScript', 'return {}\n')
        starter = item(self.tree.getroot(), 'StarterPlayer', 'StarterPlayer')
        scripts = item(starter, 'StarterPlayerScripts', 'StarterPlayerScripts')
        client = item(scripts, 'Game1Client', 'LocalScript', 'print("client")\n')
        self.creation = item(item(client, 'character', 'Folder'), 'Creation', 'ModuleScript', 'return 1\n')
        self.client = client
        server = item(self.tree.getroot(), 'ServerScriptService', 'ServerScriptService')
        item(server, 'Game1Server', 'Script', 'print("server")\n')
        self.tree.write(self.source, encoding='utf8')

    def test_matching_sources_are_verified_before_and_after_compilation(self):
        builder = RuntimePlaceBuilder(self.root)
        result = builder.inspect(self.rows)
        self.assertEqual(result['scriptCount'], 4)
        compiled = builder.prepare(self.rows, expected_sha=result['sourceSha256'], snapshot_id=1, catalog_digest='test')
        report = json.loads(Path(compiled['reportPath']).read_text())
        self.assertEqual(report['scriptSha256'], result['scriptSha256'])
        self.assertEqual(verify_scripts(self.root, ET.parse(compiled['runtimePath'])),
                         {'scriptCount': 4, 'scriptSha256': result['scriptSha256']})

    def test_stale_source_missing_module_extra_module_and_disabled_bootstrap(self):
        original = self.creation.find('./Properties/ProtectedString')
        original.text = 'return 0\n'
        with self.assertRaisesRegex(ValueError, 'stale .*Creation'):
            verify_scripts(self.root, self.tree)
        original.text = 'return 1\n'
        folder = self.client.find('./Item[@class="Folder"]')
        folder.remove(self.creation)
        with self.assertRaisesRegex(ValueError, 'missing .*Creation'):
            verify_scripts(self.root, self.tree)
        folder.append(self.creation)
        extra = item(folder, 'Old', 'ModuleScript', 'return {}')
        with self.assertRaisesRegex(ValueError, 'unexpected .*Old'):
            verify_scripts(self.root, self.tree)
        folder.remove(extra)
        ET.SubElement(self.client.find('Properties'), 'bool', name='Disabled').text = 'true'
        with self.assertRaisesRegex(ValueError, 'disabled .*Game1Client'):
            verify_scripts(self.root, self.tree)

    def test_line_endings_and_bom_are_not_source_differences(self):
        self.creation.find('./Properties/ProtectedString').text = '\ufeffreturn 1\r\n'
        self.assertEqual(verify_scripts(self.root, self.tree)['scriptCount'], 4)

    def test_new_source_after_preflight_stops_build(self):
        builder = RuntimePlaceBuilder(self.root)
        result = builder.inspect(self.rows)
        (self.root / 'src/client/character/Creation.luau').write_text('return 2\n')
        with self.assertRaisesRegex(ValueError, 'stale .*Creation'):
            builder.prepare(self.rows, expected_sha=result['sourceSha256'], snapshot_id=1, catalog_digest='test')
        self.assertFalse(builder.destination.exists())

    def test_missing_truncated_invalid_have_distinct_diagnostics(self):
        self.source.unlink()
        with self.assertRaisesRegex(ValueError, 'Source XML missing'):
            RuntimePlaceBuilder(self.root).inspect(self.rows)
        self.source.write_bytes(b'abc')
        with self.assertRaisesRegex(ValueError, 'empty or truncated'):
            _parse(self.source)
        self.source.write_bytes(b'x' * 201)
        with self.assertRaisesRegex(ValueError, 'not a valid Roblox XML'):
            _parse(self.source)

    def test_production_builder_requires_rojo_project(self):
        (self.root / 'default.project.json').unlink()
        with self.assertRaisesRegex(ValueError, 'default.project.json is missing'):
            RuntimePlaceBuilder(self.root, require_scripts=True).inspect(self.rows)

    def test_actual_project_maps_client_server_shared(self):
        scripts, scopes = expected_scripts(ROOT)
        self.assertIn(('StarterPlayer', 'StarterPlayerScripts', 'Game1Client'), scripts)
        self.assertIn(('ServerScriptService', 'Game1Server'), scripts)
        self.assertIn(('ReplicatedStorage', 'Game1Shared', 'RuntimeVersion'), scripts)
        self.assertEqual(len(scopes), 3)


class ClientContracts(unittest.TestCase):
    def test_asset_status_and_timeout_before_preview_replacement(self):
        preloader = read('src/client/character/CharacterCreationMeshPreloader.luau')
        self.assertIn('status == Enum.AssetFetchStatus.Success', preloader)
        self.assertIn('if ok and callbackSeen and success then', preloader)
        self.assertIn('return successful == #queue and current(), geometryReady and current()', preloader)
        self.assertIn('activeCount >= MAX_CONCURRENT', preloader)
        self.assertIn('os.clock() >= deadline', preloader)
        preview = read('src/client/character/CharacterCreationPreviewController.luau')
        self.assertLess(preview.index('MeshPreloader.PreloadModel(instance'), preview.index('instance.Parent = self.folder'))

    def test_warm_variants_and_late_rpc_ownership(self):
        warm = read('src/client/character/CharacterCreationVariantPrewarm.luau')
        self.assertIn('for _, group in ipairs({"hair", "head", "eyes", "eyebrows"})', warm)
        self.assertIn('choice[group] = row.id', warm)
        self.assertIn('Preview.AwaitTemplate', warm)
        self.assertIn('math.min(#queue, 24)', warm)
        remote = read('src/client/character/CharacterCreationRequest.luau')
        self.assertLess(remote.index('while active[remote]'), remote.index('remote.InvokeServer'))
        self.assertIn('if active[remote] == result then active[remote] = nil end', remote)
        self.assertIn('"request_timeout"', remote)

    def test_world_recovery_keeps_authoritative_server_gate(self):
        controller = read('src/client/character/CharacterCreationController.luau')
        self.assertIn('Panel.SetRecovery(controls', controller)
        self.assertIn('remoteFor("CharacterCreationManage")', controller)
        self.assertIn('player.Character == model and leaving', controller)
        self.assertIn('if current() and CameraController.ClearCreationView() then', controller)
        self.assertIn('Game1CharacterSceneStreamReady', controller)
        stream = read('src/server/character/CharacterCreationStreamingService.luau')
        self.assertIn('streamTokens[player] ~= token', stream)

    def test_palette_owns_exact_touch_and_mobile_layout(self):
        code = read('src/client/character/CharacterCreationColorPalette.luau')
        self.assertIn('not pointer and', code)
        self.assertIn('input == pointer', code)
        self.assertIn('if not overlay.Visible then releasePointer() end', code)
        panel = read('src/client/character/CharacterCreationPanel.luau')
        self.assertIn('viewport.Y * 0.70', panel)
        self.assertIn('local rows = 1', panel)
        language = read('src/client/localization/LanguageMenuController.luau')
        self.assertIn('height - top - footer', language)
        self.assertIn('settingsAction.Position = UDim2.fromOffset(18, top +', language)
        # Typical safe-area heights in portrait / landscape; reserve a real
        # scroll viewport even when the editor has all three visible tabs.
        for safe_height, portrait in [(320, False), (360, False), (600, True), (780, True)]:
            available = max(int(safe_height * .70), min(420, safe_height - 24)) if portrait else safe_height - 24
            self.assertGreaterEqual(available - (88 + 40 + 12) - 64 - 8, 80)

    def test_compiled_runtime_debug_requires_dev_place_not_studio(self):
        policy = read('src/shared/dev/PublishedDebugAccess.luau')
        self.assertIn('Game1LocationRuntimeManifest', policy)
        self.assertIn('not compiledRuntime()', policy)
        self.assertIn('if not publishedPlaceAllowed() then return false end', policy)
        self.assertIn('if RunService:IsStudio() then return true end', policy)


if __name__ == '__main__':
    unittest.main()
