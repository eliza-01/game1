"""M454 self-contained tests, independent of the operator's changing SQLite DB."""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from location_asset_store import LocationAssetStore
from migrations.m454_flora_keep_two_retire_bush01 import migrate, KEEP_TREES, RETIRE_TREES


class FloraM454(unittest.TestCase):
    @staticmethod
    def add_asset(store: LocationAssetStore, slug: str, category: str, mesh_options=None):
        sha = 'a' * 64
        with store.connect() as db:
            db.execute('''INSERT INTO location_assets
                (slug,name_en,category,model_path,model_sha256,model_asset_id,
                model_published_sha256,model_moderation_state,revision,created_at,
                updated_at,mesh_options_json,appearance_mode,visual_material,visual_color)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (slug, slug, category, f'assets/source/{slug}.fbx', sha,
                 '83265019701312', sha, 'Approved', 1, 1.0, 1.0,
                 json.dumps(mesh_options or {}), 'material', 'Plastic', '#FFFFFF'))
            db.execute('''INSERT INTO location_asset_publications
                (asset_slug,kind,revision,asset_id,operation_path,sha256,moderation_state,published_at)
                VALUES (?,?,?,?,?,?,?,?)''',
                (slug, 'model', 1, '83265019701312', 'operations/test', sha, 'Approved', 1.0))

    def test_two_atlases_restore_published_status_without_model_reupload(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            store = LocationAssetStore(root)
            self.add_asset(store, 'thuja_02', 'tree', {
                'leaf_01': {'appearanceMode': 'material_atlas', 'atlasVariantId': 71},
                'thuja_02': {'appearanceMode': 'material_atlas', 'atlasVariantId': 85},
            })
            with store.connect() as db:
                db.executemany('INSERT INTO texture_atlas_families(id,atlas_key,created_at) VALUES (?,?,?)',
                               [(34, 'leaves_n_flowers', 1.0), (60, 'thuja_02', 1.0)])
                db.executemany('''INSERT INTO texture_atlas_variants
                    (id,family_id,width,height,filename,original_filename,source_path,
                    source_sha256,uses_alpha,published_id,published_sha256,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''', [
                    (71, 34, 8, 8, 'leaves_n_flowers_8x8_atlas.png',
                     'leaves_n_flowers_8x8_atlas.png', 'unused.png', '1'*64, 1,
                     '82028913618222', '1'*64, 1.0),
                    (85, 60, 8, 8, 'thuja_02_8x8_atlas.png',
                     'thuja_02_8x8_atlas.png', 'unused.png', '2'*64, 1,
                     None, '', 1.0),
                ])
            before = store.get('thuja_02')
            self.assertEqual(before['status'], 'UPDATE_AVAILABLE')
            self.assertFalse(before['meshAtlasesCurrent'])
            self.assertEqual(before['meshOptions']['leaf_01']['texture_asset_id'], '82028913618222')
            self.assertEqual(before['meshOptions']['thuja_02']['texture_asset_id'], '')
            original_model = before['model_asset_id']
            with store.connect() as db:
                db.execute("UPDATE texture_atlas_variants SET published_id=?, published_sha256=source_sha256 "
                           "WHERE id=85", ('998877665544',))
            after = store.get('thuja_02')
            self.assertTrue(after['meshAtlasesCurrent'])
            self.assertEqual(after['status'], 'PUBLISHED')
            self.assertEqual(after['model_asset_id'], original_model)
            self.assertEqual(after['meshOptions']['thuja_02']['texture_asset_id'], '998877665544')
            store.export()
            generated = (root / 'src/shared/world/LocationAssetRegistry.luau').read_text('utf-8')
            self.assertIn('998877665544', generated)

    def test_migration_preserves_other_flora_and_shared_atlas_history(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            store = LocationAssetStore(root)
            for name in (*KEEP_TREES, *RETIRE_TREES):
                self.add_asset(store, name, 'tree')
            for name in ('bush_01', 'bush_02'):
                self.add_asset(store, name, 'bush')
            self.add_asset(store, 'house_01', 'building')
            with store.connect() as db:
                db.execute('INSERT INTO texture_atlas_families(id,atlas_key,created_at) VALUES (?,?,?)',
                           (1,'shared_flora',1.0))
                db.execute('''INSERT INTO texture_atlas_variants
                    (id,family_id,width,height,filename,original_filename,source_path,
                    source_sha256,uses_alpha,published_id,published_sha256,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (7, 1, 8, 8, 'shared_flora_8x8_atlas.png', 'shared_flora_8x8_atlas.png',
                     'unused.png', 'f'*64, 0, '987654', 'f'*64, 1.0))
            store.export()
            manifests = ['assets/manifests/location-assets.json',
                         'src/shared/world/LocationAssetRegistry.luau']
            originals = {name: (root / name).read_bytes() for name in manifests}
            result = migrate(root)
            self.assertTrue(result['ok'])
            self.assertEqual({row['slug'] for row in result['retired']}, RETIRE_TREES | {'bush_01'})
            self.assertEqual(set(result['retainedTrees']), KEEP_TREES)
            self.assertEqual(result['remainingBushes'], ['bush_02'])
            backup = root / result['backup']
            self.assertTrue((backup / 'game1.db').is_file())
            for name in manifests:
                self.assertEqual((backup / name).read_bytes(), originals[name])
            with closing(sqlite3.connect(root / '.control-center/game1.db')) as db:
                remaining = {row[0] for row in db.execute('SELECT slug FROM location_assets')}
                self.assertEqual(db.execute('SELECT published_id FROM texture_atlas_variants WHERE id=7').fetchone()[0], '987654')
                self.assertEqual(db.execute("SELECT model_asset_id FROM location_assets WHERE slug='thuja_02'").fetchone()[0], '83265019701312')
            self.assertEqual(remaining, set(KEEP_TREES) | {'bush_02','house_01'})
            manifest = json.loads((root / manifests[0]).read_text('utf-8'))
            self.assertEqual({x['slug'] for x in manifest['items']}, remaining)
            self.assertNotIn('"bush_01"', (root / manifests[1]).read_text('utf-8'))
            self.assertTrue(migrate(root)['alreadyMigrated'])

    def test_unreviewed_tree_aborts_before_backup(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            db_path = root / '.control-center/game1.db'
            db_path.parent.mkdir(parents=True)
            with closing(sqlite3.connect(db_path)) as db:
                db.execute('CREATE TABLE location_assets(slug TEXT,category TEXT)')
                db.executemany('INSERT INTO location_assets VALUES (?,?)',
                               [(slug,'tree') for slug in (*KEEP_TREES, *RETIRE_TREES, 'new_tree')])
                db.commit()
            with self.assertRaisesRegex(ValueError, 'unreviewed trees'):
                migrate(root)
            self.assertFalse((root / '.control-center/backups').exists())

    def test_publication_js_policy(self):
        output = subprocess.run(['node', 'system/verify/location_mesh_atlas_publication_m454.js'],
                                cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(output.returncode, 0, output.stderr or output.stdout)


if __name__ == '__main__':
    unittest.main()
