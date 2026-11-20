"""M388a: bounded chunked Runtime manifest, no reduction of selected placements."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system' / 'control-center'))
from services.location_runtime_build import (
    RuntimePlaceBuilder, _embed_runtime_manifest, _read_embedded_manifest,
    _manifest_segments, _runtime_payload, _property, RUNTIME_MANIFEST_NAME,
    RUNTIME_INLINE_BYTES, RUNTIME_CHUNK_BYTES,
)
from services.location_streaming_config import DEFAULT_SETTINGS


class RuntimeManifestTransportTests(unittest.TestCase):
    def test_inline_compatible_with_existing_runtime(self):
        payload = _runtime_payload([], snapshot_id=1, catalog_digest='test', houses={
            'types': {'house_level5_01': {'mode': 'full'}},
            'placements': [{'slug': 'house_level5_01', 'plotIndex': 1}],
        })
        text, chunks = _manifest_segments(payload)
        self.assertEqual(chunks, [])
        self.assertEqual(json.loads(text), payload)
        xml = ET.Element('roblox')
        ET.SubElement(xml, 'Item', {'class': 'ReplicatedStorage', 'referent': 'RBX_RS'})
        marker = _embed_runtime_manifest(ET.ElementTree(xml), payload)
        self.assertEqual(marker.get('class'), 'StringValue')
        self.assertEqual(len(marker.findall('./Item')), 0)
        self.assertEqual(_read_embedded_manifest(marker), payload)

    def test_large_manifest_roundtrips_and_rejects_corrupt_chunk(self):
        # More than 180 kB; no hardcoded cap on selected placements.
        frame = [0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1]
        houses = {'types': {'house_level5_01': {'mode': 'full', 'parts': []}},
                  'placements': [
                      {'slug': 'house_level5_01', 'plotIndex': i,
                       'path': ['Workspace', 'Plots', f'plot_{i:02}'],
                       'pivot': frame, 'scale': 1}
                      for i in range(1, 40)]}
        payload = _runtime_payload([], snapshot_id=1, catalog_digest='test', houses=houses)
        # Grow one syntactically valid placement list, mirroring Location data.
        # Runtime transport is deliberately independent of the Game1 registry.
        payload['targets'] = ['stone_fence_02']
        payload['modes'] = {'stone_fence_02': 'full'}
        payload['placements'] = [
            {'id': f'uuid-{i:05}', 'slug': 'stone_fence_02',
             'pivot': [i * 3.2, *frame[1:]], 'cframe': [i * 3.2, *frame[1:]],
             'size': [3.01, 4.02, 5.03]}
            for i in range(1400)]
        header, chunks = _manifest_segments(payload)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(0 < len(part.encode('utf-8')) <= RUNTIME_CHUNK_BYTES for part in chunks))
        self.assertGreater(len(''.join(chunks)), RUNTIME_INLINE_BYTES)
        self.assertLess(len(header), RUNTIME_INLINE_BYTES)
        tree = ET.ElementTree(ET.Element('roblox'))
        ET.SubElement(tree.getroot(), 'Item', {'class': 'ReplicatedStorage', 'referent': 'RBX_RS'})
        marker = _embed_runtime_manifest(tree, payload)
        self.assertEqual(_read_embedded_manifest(marker), payload)
        corrupted = copy.deepcopy(marker)
        first = corrupted.find('./Item')
        first_value = _property(first, 'string', 'Value')
        first_value.text = 'X' + first_value.text[1:]
        with self.assertRaisesRegex(RuntimeError, 'checksum mismatch'):
            _read_embedded_manifest(corrupted)
        missing = copy.deepcopy(marker)
        missing.remove(missing.find('./Item'))
        with self.assertRaisesRegex(RuntimeError, 'transport'):
            _read_embedded_manifest(missing)

    def test_e2e_saved_place_large_manifest_preserves_authoring_and_colliders(self):
        from test_location_runtime_build import fixture
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, rows = fixture(root)
            tree = ET.parse(source)
            folder = next(n for n in tree.iter('Item') if n.get('class') == 'Folder')
            example = next(n for n in folder.findall('Item') if n.get('class') == 'Model'
                           and 'stone_fence_02' in (n.find("./Properties/string[@name='Name']").text or ''))
            original_row = rows[0]
            # Each new copied model has unique Roblox referents and scan ID.
            for index in range(2, 1900):
                clone = copy.deepcopy(example)
                full_name = f'stone_fence_02__{index:06d}'
                clone.find("./Properties/string[@name='Name']").text = full_name
                for child in clone.iter('Item'):
                    child.set('referent', f'RBX_EXTRA_{index}_{child.get("class")}')
                folder.append(clone)
                entry = copy.deepcopy(original_row)
                entry['placementId'] = f'uuid-{index}'
                entry['path'] = f'Workspace.Fences.{full_name}'
                rows.append(entry)
            tree.write(source, encoding='utf-8', xml_declaration=True)
            before = source.read_bytes()
            builder = RuntimePlaceBuilder(root)
            inspected = builder.inspect(rows)
            result = builder.prepare(rows, expected_sha=inspected['sourceSha256'],
                                     snapshot_id=1, catalog_digest='test')
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(Path(result['backupPath']).read_bytes(), before)
            runtime = ET.parse(result['runtimePath'])
            marker = next(node for node in runtime.iter('Item') if node.get('class') == 'StringValue'
                          and node.find("./Properties/string[@name='Name']") is not None
                          and node.find("./Properties/string[@name='Name']").text == RUNTIME_MANIFEST_NAME)
            self.assertGreater(len(marker.findall('./Item')), 1)
            data = _read_embedded_manifest(marker)
            self.assertEqual(len(data['placements']), len(rows))
            self.assertEqual(len([n for n in runtime.iter('Item') if n.get('class') == 'MeshPart']), 0)
            self.assertEqual(len([n for n in runtime.iter('Item') if n.get('class') == 'Part']), len(rows))
            self.assertFalse(data['publishAllowed'])

    def test_client_server_read_same_shared_transport(self):
        contract = (ROOT / 'src/shared/world/LocationRuntimeManifestContract.luau').read_text(encoding='utf-8')
        server = (ROOT / 'src/server/world/LocationLodTemplateService.luau').read_text(encoding='utf-8')
        client = (ROOT / 'src/client/world/LocationWorldStreamer.luau').read_text(encoding='utf-8')
        self.assertIn('function Contract.ReadManifest(marker)', contract)
        self.assertIn('Contract.ReadManifest(marker)', server)
        self.assertIn('Contract.ReadManifest(marker)', client)
        self.assertIn('return decodeJson(assembled)', contract)
        self.assertIn('Contract.Validate(manifest, Registry)', server)
        self.assertIn('Contract.Validate(candidate, Registry)', client)


if __name__ == '__main__':
    unittest.main()
