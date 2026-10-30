"""Behavioral tests for extracted M52/M53 source-only invariants."""

from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "system/verify"))
from validators.source_only import check_source_only_contract


SOURCE_ONLY_MIGRATION_MARKERS = (
    'def migrate_source_only_assets',
    '"game1-source-only-assets-v1"',
    '"assets/prepared/"',
    '"assets/source/"',
    '"prepared-wins"',
    '"source-wins"',
    '"prepared-before"',
)
MIGRATION_CALL = 'migrate_source_only_assets(ROOT, ROOT / ".control-center" / "game1.db")'
STORE_NAMES = (
    'character_store.py', 'character_core/identity.py',
    'animation_core/storage.py', 'weapon_store.py',
    'monster_store.py', 'monster_animation_store.py',
)


class SourceOnlyValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix='game1-verify-source-only-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.write('system/control-center/source_only_assets.py', '\n'.join(SOURCE_ONLY_MIGRATION_MARKERS))
        self.write('system/control-center/migrate.py', MIGRATION_CALL)
        for name in STORE_NAMES:
            self.write(f'system/control-center/{name}', '# valid active store\n')
        self.items = [{
            'slug': 'fence',
            'model_path': 'assets/source/location-assets/fence/model.fbx',
            'texture_path': 'assets/source/texture-atlases/stone.jpg',
            'atlasVariantId': 'stone',
        }]
        self.write_json('assets/manifests/location-assets.json', {
            'schemaVersion': 4, 'items': self.items,
        })
        self.inputs = {
            'location_asset_store_text': '\n'.join((
                'model_path TEXT NOT NULL DEFAULT \'\'',
                'texture_path TEXT NOT NULL DEFAULT \'\'',
                'self.root / "assets/source/location-assets"',
            )),
            'deco_assets_js_text': 'const texture = row.texture_path;',
            'host_agent_text': MIGRATION_CALL,
            'character_js_text': 'character source path',
            'ui_html': '<main>asset manager</main>',
        }

    def write(self, relative: str, contents: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding='utf-8')
        return path

    def write_json(self, relative: str, value: dict) -> Path:
        return self.write(relative, json.dumps(value))

    def check(self) -> list[str]:
        errors: list[str] = []
        check_source_only_contract(self.root, errors.append, **self.inputs)
        return errors

    def test_valid_canonical_and_atlas_registry_paths(self):
        self.assertEqual(self.check(), [])

    def test_legacy_reference_does_not_need_own_texture_path(self):
        self.items[0]['texture_reference_slug'] = 'stone-fence'
        self.items[0]['texture_path'] = ''
        self.write_json('assets/manifests/location-assets.json', {
            'schemaVersion': 4, 'items': self.items,
        })
        self.assertEqual(self.check(), [])

    def test_m52_rejects_noncanonical_and_legacy_fields(self):
        self.items[0]['model_path'] = 'assets/prepared/fence.fbx'
        self.items[0]['texture_path'] = 'assets/source/location-assets/not-an-atlas.jpg'
        self.items[0]['texture_prepared_path'] = 'assets/prepared/texture.png'
        self.write_json('assets/manifests/location-assets.json', {
            'schemaVersion': 4, 'items': self.items,
        })
        errors = self.check()
        self.assertEqual(errors[:3], [
            'm52 Location Asset model path is not canonical source-only: fence',
            'm52 owned Location Asset texture path is not canonical source-only: fence',
            'm52 manifest still exports legacy field texture_prepared_path: fence',
        ])
        self.assertIn('m53 manifests still reference assets/prepared: location-assets.json', errors)

    def test_m53_rejects_stale_prepared_files_and_store_paths(self):
        self.write('assets/prepared/obsolete.fbx', 'obsolete')
        self.write('assets/manifests/obsolete.json', '{"path":"assets/prepared/obsolete.fbx"}')
        self.write('system/control-center/monster_store.py', 'self.root / "assets/prepared/monster"')
        errors = self.check()
        self.assertIn('m53 source-only migration incomplete: assets/prepared still has 1 file(s)', errors)
        self.assertIn('m53 manifests still reference assets/prepared: obsolete.json', errors)
        self.assertIn('m53 active store can still create assets/prepared: system/control-center/monster_store.py', errors)

    def test_m53_empty_legacy_directory_also_rejected(self):
        (self.root / 'assets/prepared').mkdir(parents=True)
        self.assertIn('m53 source-only migration incomplete: empty assets/prepared tree still exists', self.check())

    def test_m53_database_rejects_split_and_noncanonical_aliases(self):
        db = self.root / '.control-center/game1.db'
        db.parent.mkdir(parents=True)
        with closing(sqlite3.connect(db)) as con, con:
            con.execute('CREATE TABLE characters (source_path TEXT, prepared_path TEXT)')
            con.execute('INSERT INTO characters VALUES (?,?)', ('assets/source/a.fbx', 'assets/prepared/a.fbx'))
            con.execute('CREATE TABLE weapons (model_source_path TEXT, model_prepared_path TEXT)')
            con.execute('INSERT INTO weapons VALUES (?,?)', ('outside/source.fbx', 'outside/source.fbx'))
        self.assertEqual(self.check(), [
            'm53 characters still has split Source/Prepared paths',
            'm53 weapons canonical path is outside assets/source: outside/source.fbx',
        ])

    def test_m53_missing_migration_contract_preserves_diagnostic_order(self):
        self.write('system/control-center/migrate.py', 'pass')
        self.inputs['host_agent_text'] = ''
        self.assertEqual(self.check(), [
            'm53 Control Center startup does not run source-only migration before stores',
            'm53 migrate.py does not run project-wide source-only migration',
        ])

    def test_valid_check_does_not_modify_existing_source_bytes(self):
        source = self.root / 'assets/manifests/location-assets.json'
        original = source.read_bytes()
        self.assertEqual(self.check(), [])
        self.assertEqual(source.read_bytes(), original)
        self.assertFalse((self.root / '.control-center').exists())
        self.assertFalse((self.root / 'assets/prepared').exists())


if __name__ == '__main__':
    unittest.main()
