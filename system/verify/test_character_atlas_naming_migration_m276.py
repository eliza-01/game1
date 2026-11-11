"""M276: real Atlas Registry schema, stable ID migration, conflict isolation."""
from pathlib import Path
import sys
import tempfile
import unittest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services.texture_atlas_registry import AtlasRegistry
from services.character_atlas_migration import migrate


class CharacterAtlasM276(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / '.control-center').mkdir(parents=True)
        self.registry = AtlasRegistry(self.root)
        # Character Armor v2 owns this table in the real project.
        with self.registry.connect() as db:
            db.execute("""CREATE TABLE character_appearances (
                id TEXT PRIMARY KEY, atlas_variant_id INTEGER NOT NULL UNIQUE,
                material_json TEXT NOT NULL DEFAULT '{}', created_at REAL NOT NULL)""")

    def add_atlas(self, key, dims, color, asset_id):
        width, height = dims
        source = self.root / f'{key}_{width}x{height}_atlas.png'
        Image.new('RGBA', dims, color).save(source)
        row = self.registry.register_file(source, domain='character')
        with self.registry.connect() as db:
            db.execute('''UPDATE texture_atlas_variants
                SET published_id=?,published_sha256=source_sha256 WHERE id=?''', (asset_id, row['id']))
        return row['id']

    def test_rename_preserves_publication_bytes_and_variants(self):
        a = self.add_atlas('newborn_upper', (16, 16), (12, 34, 56, 255), '111')
        b = self.add_atlas('newborn_upper', (8, 8), (15, 66, 77, 255), '222')
        h = self.add_atlas('head_01_male', (16, 16), (11, 15, 18, 255), '333')
        with self.registry.connect() as db:
            db.execute('''INSERT INTO texture_atlas_bindings
                (consumer_type,consumer_id,variant_id,revision,changed_at,synced_revision)
                VALUES('character_part','newborn_upper',?,3,1,0)''', (a,))
        preview = migrate(self.root)
        self.assertEqual(len(preview['changes']), 3)
        self.assertEqual(self.registry.get_variant(a)['atlas_key'], 'newborn_upper')
        result = migrate(self.root, apply=True)
        self.assertTrue(Path(result['backup']).is_file())
        self.assertEqual(result['legacyBindingsArchived'], 1)
        for variant, key, image_id in ((a, 'human_common_m001_t001_upper', '111'),
                                       (b, 'human_common_m001_t001_upper', '222'),
                                       (h, 'human_male_m001_t001_head', '333')):
            actual = self.registry.get_variant(variant)
            self.assertEqual(actual['atlas_key'], key)
            self.assertEqual(actual['published_id'], image_id)
            self.assertTrue(actual['current'])
            self.assertTrue((self.root / actual['source_path']).is_file())
        self.assertEqual(self.registry.catalog(domain='character')[0]['atlasKey'],
                         'human_common_m001_t001_upper')
        self.assertEqual(migrate(self.root, apply=True)['changes'], [])
        with self.registry.connect() as db:
            self.assertIsNone(db.execute('''SELECT 1 FROM texture_atlas_bindings
                WHERE consumer_id='newborn_upper' ''').fetchone())
            self.assertEqual(db.execute('SELECT count(*) FROM character_atlas_name_migrations_m276').fetchone()[0], 3)
            self.assertEqual(db.execute('SELECT count(*) FROM character_atlas_legacy_bindings_m276').fetchone()[0], 1)

    def test_same_publication_merge_uses_existing_canonical_id(self):
        old = self.add_atlas('newborn_lower', (16, 8), (11, 22, 33, 255), '123456')
        # Same pixels and published ID, but a separately registered canonical row.
        new = self.add_atlas('human_common_m001_t001_lower', (16, 8), (11, 22, 33, 255), '123456')
        with self.registry.connect() as db:
            db.execute('''INSERT INTO texture_atlas_bindings
                (consumer_type,consumer_id,variant_id,revision,changed_at,synced_revision)
                VALUES('character_part','newborn_lower',?,5,1,1)''', (old,))
            db.execute("""INSERT INTO character_appearances(id,atlas_variant_id,created_at)
                VALUES('atlas_legacy_lower',?,1)""", (old,))
        outcome = migrate(self.root, apply=True)
        self.assertEqual(outcome['changes'][0]['operation'], 'merge')
        self.assertEqual(outcome['changes'][0]['targetVariantId'], new)
        self.assertTrue(self.registry.get_variant(old)['retired'])
        self.assertFalse(self.registry.get_variant(new)['retired'])
        with self.registry.connect() as db:
            self.assertEqual(db.execute("SELECT atlas_variant_id FROM character_appearances WHERE id='atlas_legacy_lower'").fetchone()[0], new)
            self.assertEqual(db.execute("SELECT variant_id FROM character_atlas_legacy_bindings_m276 WHERE consumer_id='newborn_lower'").fetchone()[0], new)
            self.assertEqual(db.execute('SELECT count(*) FROM texture_atlas_publications WHERE variant_id=?', (old,)).fetchone()[0], 0)
        self.assertEqual(len(self.registry.catalog(domain='character')), 1)

    def test_conflicting_target_blocks_without_change(self):
        old = self.add_atlas('newborn_lower', (16, 8), (11, 22, 33, 255), '123456')
        self.add_atlas('human_common_m001_t001_lower', (16, 8), (15, 22, 33, 255), '654321')
        with self.assertRaisesRegex(ValueError, 'different content'):
            migrate(self.root, apply=True)
        self.assertEqual(self.registry.get_variant(old)['atlas_key'], 'newborn_lower')
        self.assertFalse(list((self.root / '.control-center/backups').glob('before_character_atlas_names_m276_*')))

    def test_missing_source_blocks_before_database_change(self):
        old = self.add_atlas('newborn_boots', (8, 8), (11, 22, 33, 255), '1456')
        path = self.root / self.registry.get_variant(old)['source_path']
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'stored atlas missing'):
            migrate(self.root, apply=True)
        self.assertEqual(self.registry.get_variant(old)['atlas_key'], 'newborn_boots')

    def test_other_sections_untouched(self):
        fn = self.root / 'newborn_upper_8x8_atlas.png'
        Image.new('RGB', (8, 8), (11, 22, 33)).save(fn)
        item = self.registry.register_file(fn, domain='location')
        with self.assertRaisesRegex(ValueError, 'not Character-scoped'):
            migrate(self.root)
        self.assertEqual(self.registry.get_variant(item['id'])['atlas_key'], 'newborn_upper')


if __name__ == '__main__':
    unittest.main()
