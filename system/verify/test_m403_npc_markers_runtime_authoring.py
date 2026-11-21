"""M403: independent NPC Studio toggle and removal of editor geometry from DEV."""
from pathlib import Path
import sys
import tempfile
import unittest
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system' / 'control-center'))
from services.location_runtime_build import RuntimePlaceBuilder
from test_location_runtime_build import fixture


def named_item(parent, klass, name, referent):
    obj = ET.SubElement(parent, 'Item', {'class': klass, 'referent': referent})
    ET.SubElement(ET.SubElement(obj, 'Properties'), 'string', name='Name').text = name
    return obj


class AuthoringRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.file, self.rows = fixture(self.root)
        tree = ET.parse(self.file)
        workspace = next(n for n in tree.getroot() if n.get('class') == 'Workspace')
        authoring = named_item(workspace, 'Folder', 'Game1Authoring', 'RBX_AUTH')
        locations = named_item(authoring, 'Folder', 'Locations', 'RBX_LOC')
        location = named_item(locations, 'Model', 'Location_Main', 'RBX_LMODEL')
        named_item(location, 'Part', 'Edge_001', 'RBX_EDGE')
        spawns = named_item(authoring, 'Folder', 'NpcSpawns', 'RBX_NPC_F')
        spawn = named_item(spawns, 'Model', 'Npc_guard', 'RBX_NPC')
        named_item(spawn, 'Part', 'Direction', 'RBX_NPC_PART')
        self.xml = tree
        self.xml.write(self.file, encoding='utf-8', xml_declaration=True)
        self.builder = RuntimePlaceBuilder(self.root)

    def test_preflight_reports_authoring_and_runtime_strips_entire_folder(self):
        source = self.file.read_bytes()
        preflight = self.builder.inspect(self.rows)
        self.assertEqual(preflight['authoringMarkersToStrip'], 7)
        result = self.builder.prepare(self.rows, expected_sha=preflight['sourceSha256'],
                                      snapshot_id=213, catalog_digest='marker-test')
        runtime = ET.parse(result['runtimePath'])
        names = [prop.text for prop in runtime.findall('.//Properties/string[@name="Name"]')]
        self.assertNotIn('Game1Authoring', names)
        self.assertNotIn('Locations', names)
        self.assertNotIn('Edge_001', names)
        self.assertNotIn('NpcSpawns', names)
        self.assertNotIn('Direction', names)
        self.assertIn('UnmanagedPackage', names)
        self.assertEqual(self.file.read_bytes(), source)
        self.assertEqual(Path(result['backupPath']).read_bytes(), source)
        self.assertEqual(result['removedAuthoringInstances'], 7)

    def test_authoring_folder_absent_is_allowed(self):
        tree = ET.parse(self.file)
        workspace = next(n for n in tree.getroot() if n.get('class') == 'Workspace')
        authoring = next(n for n in workspace if n.get('class') == 'Folder' and n.findtext('./Properties/string[@name="Name"]') == 'Game1Authoring')
        workspace.remove(authoring)
        tree.write(self.file, encoding='utf-8', xml_declaration=True)
        info = self.builder.inspect(self.rows)
        self.assertEqual(info['authoringMarkersToStrip'], 0)
        runtime = self.builder.prepare(self.rows, expected_sha=info['sourceSha256'],
                                       snapshot_id=214, catalog_digest='no-markers')
        self.assertTrue(Path(runtime['runtimePath']).is_file())

    def test_unsafe_reference_prevents_preflight_and_cannot_strip(self):
        tree = ET.parse(self.file)
        house = next(n for n in tree.iter('Item') if n.get('referent') == 'RBX_OTHER')
        ET.SubElement(house.find('Properties'), 'Ref', name='Adornee').text = 'RBX_EDGE'
        tree.write(self.file, encoding='utf-8', xml_declaration=True)
        with self.assertRaisesRegex(ValueError, 'External reference into Game1Authoring'):
            self.builder.inspect(self.rows)
        self.assertFalse(self.builder.destination.exists())

    def test_reserved_name_never_removes_unmanaged_model(self):
        tree = ET.parse(self.file)
        root = next(n for n in tree.getroot() if n.get('class') == 'Workspace')
        folder = next(n for n in root if n.get('class') == 'Folder' and n.findtext('./Properties/string[@name="Name"]') == 'Game1Authoring')
        folder.set('class', 'Model')
        tree.write(self.file, encoding='utf-8', xml_declaration=True)
        with self.assertRaisesRegex(ValueError, 'editor-owned Folder'):
            self.builder.inspect(self.rows)


class StudioToggleContracts(unittest.TestCase):
    def test_npc_button_reuses_studio_marker_visibility_without_geometry_writes(self):
        script = (ROOT / 'system/studio-plugin/modules/StudioMarkerVisibility.luau').read_text(encoding='utf-8')
        self.assertIn('"Game1NpcSpawnMarkers"', script)
        self.assertIn('self:SetNpcVisible(not self.npcVisible)', script)
        self.assertIn('marker:GetAttribute("Game1NpcSpawnMarker")', script)
        self.assertIn('then self.npcVisible else self.visible', script)
        self.assertIn('plugin:GetSetting(NPC_SETTING_KEY)', script)
        self.assertIn('self.plugin:SetSetting(NPC_SETTING_KEY, value)', script)
        self.assertIn('self.npcVisible = true\n    pcall(function() self:_apply(self.workspace) end)', script)
        self.assertNotIn('marker:Destroy()', script)
        self.assertNotIn('marker.Parent =', script)
        installer = (ROOT / 'system/studio-plugin/install.ps1').read_text(encoding='utf-8')
        self.assertIn("'Game1AuthoringMarkers'", installer)
        self.assertIn("'Game1NpcSpawnMarkers'", installer)

    def test_cleanup_runs_before_shared_waits_and_catalog_keeps_single_owner(self):
        init = (ROOT / 'src/server/init.server.luau').read_text(encoding='utf-8')
        self.assertLess(init.index('authoringCleanup.Start()'),
                        init.index('ReplicatedStorage:WaitForChild("Game1Shared")'))
        cleanup = (ROOT / 'src/server/world/Game1AuthoringCleanupService.luau').read_text(encoding='utf-8')
        self.assertIn('if started then return end', cleanup)
        self.assertIn('Workspace.ChildAdded:Connect(removeAuthoringRoot)', cleanup)
        self.assertIn('Workspace:FindFirstChild("Game1Authoring")', cleanup)
        self.assertIn('instance:Destroy()', cleanup)
        catalog = (ROOT / 'src/server/bootstrap/ServiceCatalog.luau').read_text(encoding='utf-8')
        self.assertEqual(catalog.count('Game1AuthoringCleanupService'), 2)  # name + require


if __name__ == '__main__':
    unittest.main()
