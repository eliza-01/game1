"""M342 acceptance: dedicated COL geometry has no authoring or physics role."""
from __future__ import annotations

import importlib.util
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system' / 'control-center'))
from services.retired_col_mesh import retired, strip_mesh_rows, strip_options
from services.mesh_authoring_policy import normalize_location_options, normalize_mesh_options
from real_estate.contracts import present_parts

spec = importlib.util.spec_from_file_location('m342_migration', ROOT / 'system/verify/m342_retire_col_mesh.py')
migration = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(migration)


class ColRetirementM342(unittest.TestCase):
    def test_retirement_names_are_precise(self):
        for value in ('col_mesh', 'COL_wall', 'House_COL_Wall', 'beam_col', 'X_col_A'):
            with self.subTest(value=value):
                self.assertTrue(retired(value))
        for value in ('house', 'color', 'column', 'collision', 'colormap', 'cold'):
            with self.subTest(value=value):
                self.assertFalse(retired(value))

    def test_inspection_discards_dedicated_collision_meshes(self):
        report = {'meshes': [{'name':'house'}, {'name':'COL_mesh'}, {'name':'door'}], 'sourceSha256': 'keep'}
        filtered = strip_mesh_rows(report)
        self.assertEqual([m['name'] for m in filtered['meshes']], ['house','door'])
        self.assertEqual([m['name'] for m in report['meshes']], ['house','COL_mesh','door'])
        self.assertEqual(filtered['sourceSha256'], 'keep')
        self.assertEqual(present_parts(report), ('house','door'))

    def test_old_collision_flags_do_not_survive_registry(self):
        source = {'col_mesh': {'noCollide': False},
                  'house': {'collisionMesh':False, 'destructible':True, 'noCollide':True}}
        cleaned = strip_options(source)
        self.assertNotIn('col_mesh',cleaned)
        self.assertNotIn('collisionMesh',cleaned['house'])
        self.assertNotIn('destructible',cleaned['house'])
        self.assertTrue(source['house']['destructible'])

    def test_ordinary_visuals_remain_configurable(self):
        estate = normalize_mesh_options('house', {}, domain='estate')
        self.assertTrue(estate['noCollide'])
        self.assertEqual(estate['collisionFidelity'], 'Box')
        location = normalize_mesh_options('stone_fence', {'noCollide':False,'collisionFidelity':'Hull'}, domain='location')
        self.assertFalse(location['noCollide'])
        self.assertEqual(location['collisionFidelity'], 'Hull')
        options = normalize_location_options({'meshes':[{'name':'tree'}, {'name':'COL_mesh'}]},
             {'COL_mesh':{'collisionMesh':True}, 'tree':{'collisionMesh':False,'noCollide':True}})
        self.assertEqual(set(options), {'tree'})
        self.assertNotIn('collisionMesh',options['tree'])

    def test_studio_cleanup_is_only_retirement_path(self):
        directory=ROOT/'system/studio-plugin'
        registered=json.loads((directory/'plugin.project.json').read_text('utf-8'))['tree']['modules']
        self.assertIn('StudioRetiredColMeshCleanup',registered)
        self.assertNotIn('StudioRealEstateRigRoles',registered)
        self.assertNotIn('StudioRealEstatePlacedCollisionSync',registered)
        self.assertIn('RetiredCleanup.CleanEstate(', (directory/'modules/StudioRealEstateModel.luau').read_text('utf-8'))
        self.assertIn('RetiredCleanup.CleanLocation(', (directory/'modules/DecoAssetLoader.luau').read_text('utf-8'))

    def test_no_old_collision_row_in_real_estate_ui(self):
        s=(ROOT/'system/control-center/static/real-estate.js').read_text('utf-8')
        self.assertNotIn('realEstateIsCollider',s)
        self.assertNotIn('physics only · no image',s)
        self.assertNotIn('Collision · no texture',s)
        self.assertIn('Parts blueprint',s)

    def test_migration_dry_run_does_not_change_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); data=root/'.control-center'; data.mkdir()
            rdb=data/'game1_real_estate.db'; ldb=data/'game1.db'
            with closing(sqlite3.connect(rdb)) as c, c:
                c.executescript('''CREATE TABLE real_estate(slug TEXT,skeleton_json TEXT,textures_json TEXT,
                     model_rigs_json TEXT,mesh_options_json TEXT,mesh_sources_json TEXT);
                     CREATE TABLE real_estate_publications(id INTEGER PRIMARY KEY, part TEXT);''')
                c.execute('INSERT INTO real_estate VALUES (?,?,?,?,?,?)',('house_level1_01',
                      json.dumps({'meshes':[{'name':'house'},{'name':'col_mesh'}]}), '{}',
                      json.dumps({'house':{'assetId':'42'}, 'col_mesh':{'assetId':'43'}}),
                      json.dumps({'house':{'collisionMesh':False},'col_mesh':{'noCollide':False}}),'{}'))
                c.executemany('INSERT INTO real_estate_publications(part) VALUES (?)',
                              [('model:col_mesh',), ('model:colorful',), ('model:house',)])
            with closing(sqlite3.connect(ldb)) as c, c:
                c.execute('CREATE TABLE location_assets(slug TEXT,mesh_options_json TEXT)')
                c.execute('INSERT INTO location_assets VALUES (?,?)',('big_tree_01',json.dumps({'col_mesh':{'noCollide':False},'tree':{'collisionMesh':False}})))
            previous = (rdb.read_bytes(),ldb.read_bytes())
            # SQLite's context manager alone does not close the database.
            # Track real connections so this regression is caught on Linux too,
            # where Windows' WinError 32 does not occur.
            original_connect = sqlite3.connect
            opened = []

            class TrackedConnection(sqlite3.Connection):
                was_closed = False

                def close(self):
                    self.was_closed = True
                    super().close()

            def tracked_connect(*args, **kwargs):
                connection = original_connect(*args, factory=TrackedConnection, **kwargs)
                opened.append(connection)
                return connection

            with patch.object(migration.sqlite3, 'connect', side_effect=tracked_connect):
                report = migration.migrate(root, dry_run=True)
            self.assertEqual(len(opened), 2)
            self.assertTrue(all(c.was_closed for c in opened), 'M342 dry-run leaked an SQLite handle')
            self.assertEqual(report['retiredPublications'],1)
            self.assertEqual(report['houses'][0]['removed'],['col_mesh'])
            self.assertEqual(report['locations'][0]['removed'],['col_mesh'])
            self.assertEqual((rdb.read_bytes(),ldb.read_bytes()),previous)
            self.assertFalse((data/'backups').exists())


if __name__ == '__main__':
    unittest.main()
