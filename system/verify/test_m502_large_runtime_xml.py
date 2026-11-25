"""Regression: saved and compiled XML Places may exceed the old 150 MiB cap."""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services.location_runtime_build import RuntimePlaceBuilder, _parse, _sha
from test_location_runtime_build import fixture


class LargeRuntimeXML(unittest.TestCase):
    def test_large_place_preflight_backup_compile_and_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, rows = fixture(root)
            # Preserve real XML Item/Properties data rather than padding with
            # comments or whitespace that ElementTree would discard.
            ending = b'</roblox>'
            original = source.read_bytes()
            self.assertTrue(original.endswith(ending))
            block = b'A' * (1024 * 1024)
            with source.open('wb') as out:
                out.write(original[:-len(ending)])
                for i in range(151):
                    out.write(f'<Item class="StringValue" referent="RBX_large_{i}"><Properties><string name="Name">Large_{i}</string><string name="Value">'.encode())
                    out.write(block)
                    out.write(b'</string></Properties></Item>')
                out.write(ending)
            self.assertGreater(source.stat().st_size, 150 * 1024 * 1024)
            builder = RuntimePlaceBuilder(root)
            inspected = builder.inspect(rows)
            self.assertEqual(inspected['sourceBytes'], source.stat().st_size)
            self.assertEqual(inspected['eligible'], 2)
            result = builder.prepare(rows, expected_sha=inspected['sourceSha256'],
                                     snapshot_id=1, catalog_digest='large-xml')
            self.assertEqual(_sha(source), inspected['sourceSha256'])
            self.assertEqual(_sha(Path(result['backupPath'])), inspected['sourceSha256'])
            runtime = Path(result['runtimePath'])
            self.assertGreater(runtime.stat().st_size, 150 * 1024 * 1024)
            tree = _parse(runtime)
            values = [n.find('./Properties/string[@name="Value"]')
                      for n in tree.getroot().findall('./Item[@class="StringValue"]')
                      if (n.get('referent') or '').startswith('RBX_large_')]
            self.assertEqual(len(values), 151)
            digest = hashlib.sha256(block).digest()
            for value in values:
                self.assertEqual(hashlib.sha256(value.text.encode()).digest(), digest)
            self.assertFalse(result['publishAllowed'])

    def test_parse_memory_failure_is_not_reported_as_size_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, _ = fixture(Path(tmp))
            with patch('services.location_runtime_build.etree.parse', side_effect=MemoryError):
                with self.assertRaisesRegex(ValueError, 'Insufficient memory'):
                    _parse(source)


if __name__ == '__main__':
    unittest.main()
