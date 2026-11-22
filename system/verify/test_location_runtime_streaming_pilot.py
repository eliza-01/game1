"""Runtime visual pilot: immutable placements, bounded server templates, local visuals."""
import json
import sqlite3
import sys
import tempfile
from xml.etree import ElementTree as ET
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services.location_runtime_build import _runtime_payload, RuntimePlaceBuilder
from services.location_streaming_config import DEFAULT_SETTINGS


class RuntimeStreamingPilot(unittest.TestCase):
    def test_shared_state_policy_and_local_only_visual_owner(self):
        client = (ROOT / 'src/client/world/LocationWorldStreamer.luau').read_text(encoding='utf-8')
        policy = (ROOT / 'src/shared/world/LocationLodDistancePolicy.luau').read_text(encoding='utf-8')
        for expected in ('Policy.Resolve(distance, record.desired, manifest.distances, record.mode)',
                         'MAX_CHANGES_PER_TICK = 8', 'CanCollide = false',
                         'CanQuery = false', 'CanTouch = false',
                         'record.cframe', 'record.size', 'cameraPosition - record.pivot',
                         'record.part:Destroy()', 'RunService.Heartbeat'):
            self.assertIn(expected, client)
        self.assertIn('hysteresis = 12', policy)
        self.assertIn('lod1 = 120', policy)
        self.assertIn('hide = 400', policy)
        self.assertIn('lod2 = 260', policy)
        for forbidden in ('remote:FireServer', 'RemoteEvent', 'SetNetworkOwner',
                          'model:Destroy()', 'CollisionGroup ='):
            self.assertNotIn(forbidden, client)

    def test_owned_template_cache_supports_selected_capabilities(self):
        service = (ROOT / 'src/server/world/LocationLodTemplateService.luau').read_text(encoding='utf-8')
        contract = (ROOT / 'src/shared/world/LocationRuntimeManifestContract.luau').read_text(encoding='utf-8')
        self.assertIn('Contract.MaxTargets = 64', contract)
        self.assertIn('Contract.Variants(mode)', contract)
        self.assertIn('for _, slug in ipairs(manifest.targets)', service)
        self.assertIn('for _, variant in ipairs(Contract.Variants(manifest.modes[slug]))', service)
        self.assertIn('InsertService.LoadAsset', service)
        self.assertIn('AssetService.LoadAssetAsync', service)
        self.assertIn('template.CanCollide = false', service)
        self.assertIn('cache:SetAttribute("Ready", ready)', service)
        self.assertIn('LocationLodTemplateService', (ROOT / 'src/server/bootstrap/ServiceCatalog.luau').read_text())
        self.assertIn('LocationWorldStreamer', (ROOT / 'src/client/init.client.luau').read_text())
        self.assertIn('if not marker then', service)
        self.assertIn('StudioLodPreviewTemplates")).Start(loadPrototype)', service)

    def test_server_template_ignores_retired_collision_mesh_in_published_model(self):
        # M342 deleted COL meshes from managed Place and FBX publication, but
        # older immutable Roblox Model Asset IDs may still contain col_mesh.
        service = (ROOT / 'src/server/world/LocationLodTemplateService.luau').read_text(encoding='utf-8')
        physics = (ROOT / 'src/shared/world/MeshPhysicsCore.luau').read_text(encoding='utf-8')
        self.assertIn('not MeshPhysics.IsLocationCarrier(part)', service)
        self.assertIn('and not MeshPhysics.IsCollider(part.Name)', service)
        self.assertIn('numberVisuals += 1', service)
        self.assertIn('if numberVisuals ~= 1 then', service)
        self.assertIn('function Core.IsCollider(name: string)', physics)
        self.assertIn('lower:sub(1, 4) == "col_"', physics)
        self.assertIn('lower:find("_col_", 1, true)', physics)
        self.assertIn('lower:sub(-4) == "_col"', physics)
        self.assertNotIn('template.CanCollide = true', service)
        self.assertIn('template.CanQuery = false', service)

    def test_full_snapshot_133_compact_manifest_when_available(self):
        # Optional user dataset: this test checks their latest captured source
        # if included in the diagnostic dump. Never requires live Studio.
        db = ROOT / '.control-center/location-place-revisions.sqlite'
        if not db.exists():
            self.skipTest('Local Place Registry database not included')
        with sqlite3.connect(db) as connection:
            found = connection.execute('SELECT payload FROM location_place_revisions WHERE id=133').fetchone()
        if found is None:
            self.skipTest('Snapshot #133 not included in local project')
        revision = json.loads(zlib.decompress(found[0]))
        selected = [row for row in revision['placements'] if row['slug'] in DEFAULT_SETTINGS['modes']]
        self.assertEqual(len(selected), 201)
        payload = _runtime_payload(selected, snapshot_id=133, catalog_digest='test')
        self.assertEqual(len(payload['placements']), 201)
        self.assertEqual(len({p['id'] for p in payload['placements']}), 201)
        self.assertLess(len(json.dumps(payload).encode('utf8')), 250000)
        self.assertFalse(payload['publishAllowed'])

    def test_201_placement_offline_build_using_real_snapshot_geometry(self):
        """Runtime payload + XML removal test with actual scan positions, no Roblox network."""
        db = ROOT / '.control-center/location-place-revisions.sqlite'
        if not db.exists():
            self.skipTest('Snapshot database missing')
        with sqlite3.connect(db) as connection:
            found = connection.execute('SELECT payload FROM location_place_revisions WHERE id=133').fetchone()
        if not found:
            self.skipTest('Snapshot #133 missing')
        source_rows = json.loads(zlib.decompress(found[0]))['placements']
        rows = [row for row in source_rows if row['slug'] in DEFAULT_SETTINGS['modes']]
        self.assertEqual(len(rows), 201)
        with tempfile.TemporaryDirectory() as base:
            root = Path(base)
            place = root / 'place' / 'game1_runtime_source.rbxlx'
            place.parent.mkdir()
            xml = ET.Element('roblox', version='4')
            nodes = {}
            def directory(path):
                if path in nodes:
                    return nodes[path]
                parent_path, name = path.rsplit('.', 1) if '.' in path else ('', path)
                parent = directory(parent_path) if parent_path else xml
                kind = name if name in ('Workspace', 'ReplicatedStorage') else 'Folder'
                node = ET.SubElement(parent, 'Item', {'class':kind, 'referent':'RBX_folder_'+str(len(nodes))})
                ET.SubElement(ET.SubElement(node, 'Properties'), 'string', name='Name').text = name
                nodes[path] = node
                return node
            directory('ReplicatedStorage')
            for idx, row in enumerate(rows):
                parent_path, name = row['path'].rsplit('.', 1)
                parent = directory(parent_path)
                model = ET.SubElement(parent, 'Item', {'class':'Model', 'referent':f'RBX_MODEL_{idx}'})
                ET.SubElement(ET.SubElement(model, 'Properties'), 'string', name='Name').text = name
                for part_row in (entry for entry in row['hierarchy'] if entry.get('class') in ('MeshPart','Part')):
                    part = ET.SubElement(model, 'Item', {'class':part_row['class'],
                                                         'referent':f'RBX_PART_{idx}_{part_row["class"]}'})
                    props = ET.SubElement(part, 'Properties')
                    ET.SubElement(props, 'string', name='Name').text = part_row['name']
                    cf = ET.SubElement(props, 'CoordinateFrame', name='CFrame')
                    for key, value in zip(('X','Y','Z','R00','R01','R02','R10','R11','R12','R20','R21','R22'), part_row['cframe']):
                        ET.SubElement(cf, key).text = repr(value)
                    size = ET.SubElement(props, 'Vector3', name='size')
                    for key, value in zip(('X','Y','Z'),part_row['size']):
                        ET.SubElement(size, key).text = repr(value)
                    if part_row['class'] == 'MeshPart':
                        ET.SubElement(ET.SubElement(props,'Content',name='MeshContent'),'uri').text='rbxassetid://' + row['meshId']
            ET.ElementTree(xml).write(place,encoding='utf-8',xml_declaration=True)
            builder = RuntimePlaceBuilder(root)
            check = builder.inspect(rows)
            self.assertEqual(check['eligible'],201)
            outcome = builder.prepare(rows, expected_sha=check['sourceSha256'], snapshot_id=133, catalog_digest='test')
            tree = ET.parse(outcome['runtimePath'])
            self.assertEqual(len([n for n in tree.iter('Item') if n.get('class')=='MeshPart']),0)
            self.assertEqual(len([n for n in tree.iter('Item') if n.get('class')=='Part']),201)
            marker = next(n for n in tree.iter('Item') if n.get('class')=='StringValue')
            marker_payload = json.loads(next(n.text for n in marker.findall('./Properties/string') if n.get('name')=='Value'))
            self.assertEqual(len(marker_payload['placements']),201)
            self.assertFalse(marker_payload['publishAllowed'])
            self.assertEqual(Path(outcome['backupPath']).read_bytes(),place.read_bytes())



if __name__ == '__main__':
    unittest.main()
