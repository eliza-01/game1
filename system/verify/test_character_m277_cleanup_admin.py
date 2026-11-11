"""M277: cleanup does not touch live v2 assets; admin/default have explicit ready gate."""
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'control-center'))
from migrate_character_catalog_m277 import migrate
from character_core.assemblies import CharacterAssemblies
from sqlite_connection import connect


class LegacyCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        db_path = self.root / '.control-center' / 'game1.db'
        db_path.parent.mkdir(parents=True)
        self.db = db_path
        with connect(self.db) as db:
            db.executescript('''
                CREATE TABLE character_component_records (kind TEXT,id TEXT,rig_id TEXT,mesh_family_id TEXT,
                    model_asset_id TEXT, PRIMARY KEY(kind,id));
                CREATE TABLE character_component_sets (id TEXT);
                CREATE TABLE characters (id TEXT PRIMARY KEY,visual_mode TEXT,assembly_json TEXT);
                CREATE TABLE character_stats (character_id TEXT);
                CREATE TABLE character_assembly_history (character_id TEXT);
                CREATE TABLE character_model_assignments (target_character_id TEXT,source_character_id TEXT);
                CREATE TABLE armor_piece_variants (mesh_part_id TEXT);
                CREATE TABLE project_settings (key TEXT PRIMARY KEY,value TEXT);
                CREATE TABLE character_component_publications (component_id TEXT,asset_id TEXT);
                CREATE TABLE animation_profiles (character_id TEXT PRIMARY KEY,skeleton_signature TEXT);
                CREATE TABLE animation_clips (id TEXT PRIMARY KEY,character_id TEXT,asset_id TEXT);
                CREATE TABLE animation_bindings (id TEXT PRIMARY KEY,character_id TEXT,clip_id TEXT);
                CREATE TABLE animation_clip_documents (clip_id TEXT,animation_sha256 TEXT,document_json TEXT);
                CREATE TABLE animation_publications (clip_id TEXT,asset_id TEXT);
            ''')
            db.executemany('INSERT INTO character_component_records VALUES(?,?,?,?,?)', [
                ('part','eyes_01','human','','111'),
                ('part','newborn_upper','human','','222'),
                ('rig','human','human','','333'),
                ('part','human_common_m001_eye_l','human_female','human_common_m001','444'),
                ('part','human_female_m001_head','human_female','human_female_m001','555'),
                ('rig','human_female','human_female','','666'),
            ])
            db.execute('INSERT INTO character_component_sets VALUES(?)', ('newborn',))
            db.executemany('INSERT INTO characters VALUES(?,?,?)', [
                ('human_female','model','{}'), ('human_male','assembly','{"schema_version":1}')])
            db.execute("INSERT INTO character_component_publications VALUES('eyes_01','111')")
            db.execute("INSERT INTO project_settings VALUES('active_character_archetype_id','human_male')")
            db.execute("INSERT INTO animation_profiles VALUES('human_female','old_162_bone_skeleton')")
            db.execute("INSERT INTO animation_clips VALUES('old_idle','human_female','777')")
            db.execute("INSERT INTO animation_bindings VALUES('old_idle_binding','human_female','old_idle')")
            db.execute("INSERT INTO animation_clip_documents VALUES('old_idle','sha','{}')")
            db.execute("INSERT INTO animation_publications VALUES('old_idle','777')")

    def test_dry_run_and_apply_are_safe_and_idempotent(self):
        preview = migrate(self.root)
        self.assertFalse(preview['applied'])
        self.assertCountEqual(preview['parts'], ['eyes_01', 'newborn_upper'])
        self.assertEqual(preview['retired_animation_counts'], {
            'animation_profiles': 1, 'animation_clips': 1,
            'animation_bindings': 1, 'animation_clip_documents': 1})
        with connect(self.db) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM characters').fetchone()[0], 2)
        result = migrate(self.root, apply=True)
        self.assertTrue(result['applied'])
        self.assertTrue(Path(result['backup']).is_file())
        self.assertFalse(migrate(self.root, apply=True)['applied'])
        with connect(self.db) as db:
            self.assertEqual({r['id'] for r in db.execute('SELECT id FROM character_component_records')},
                             {'human_common_m001_eye_l','human_female_m001_head','human_female'})
            self.assertEqual(db.execute('SELECT count(*) FROM characters').fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT asset_id FROM character_component_publications').fetchone()[0], '111')
            self.assertEqual(db.execute('SELECT count(*) FROM project_settings').fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT count(*) FROM character_retired_animation_records_m277').fetchone()[0], 4)
            self.assertEqual(db.execute('SELECT count(*) FROM animation_clips').fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT asset_id FROM animation_publications').fetchone()[0], '777')

    def test_armor_references_block_cleanup(self):
        with connect(self.db) as db:
            db.execute("INSERT INTO armor_piece_variants VALUES('newborn_upper')")
        with self.assertRaisesRegex(ValueError, 'Armor v2 references'):
            migrate(self.root, apply=True)
        self.assertFalse(list((self.root/'.control-center/backups').glob('before_character_catalog_m277_*')))

    def test_unknown_legacy_parts_block_cleanup(self):
        with connect(self.db) as db:
            db.execute("INSERT INTO character_component_records VALUES('part','mystery_old_part','human','','999')")
        with self.assertRaisesRegex(ValueError, 'unreviewed legacy'):
            migrate(self.root, apply=True)

    def test_v2_character_survives_repeated_cleanup(self):
        with connect(self.db) as db:
            db.execute("UPDATE characters SET visual_mode='assembly', assembly_json='{\"schema_version\":2}' WHERE id='human_female'")
        result = migrate(self.root, apply=True)
        self.assertNotIn('human_female', result['characters'])
        with connect(self.db) as db:
            self.assertEqual(db.execute("SELECT id FROM characters WHERE id='human_female'").fetchone()[0], 'human_female')


class ProfileSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name)/'test.db'
        with connect(self.db) as db:
            db.execute('CREATE TABLE project_settings(key TEXT PRIMARY KEY,value TEXT)')
        class FakeCharacters:
            db = self.db
            def __init__(self):
                self.ready=False; self.exports=0
            def get(self, key):
                if key != 'human_female': return None
                return dict(id=key,visual_mode='assembly',assembly={'schema_version':2},
                    assembly_resolved={'ready':self.ready,'missing':([] if self.ready else ['armor upper'])})
            def export(self): self.exports+=1
        self.characters=FakeCharacters()
        self.owner=object.__new__(CharacterAssemblies)
        self.owner.db=self.db
        self.owner.characters=self.characters
        self.owner.snapshot=lambda: {'saved': True}

    def test_admin_rejects_drafts_and_keeps_default_independent(self):
        with self.assertRaisesRegex(ValueError,'not ready'):
            self.owner.select_profile('human_female','admin')
        with connect(self.db) as db:self.assertEqual(db.execute('SELECT count(*) FROM project_settings').fetchone()[0],0)
        self.characters.ready=True
        self.owner.select_profile('human_female','admin')
        with connect(self.db) as db:
            self.assertEqual(db.execute('SELECT value FROM project_settings WHERE key=?', ('studio_admin_assembly_id',)).fetchone()[0], 'human_female')
            self.assertIsNone(db.execute('SELECT value FROM project_settings WHERE key=?', ('default_character_assembly_id',)).fetchone())
        self.owner.select_profile('human_female','default')
        with connect(self.db) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM project_settings').fetchone()[0],2)
        self.assertEqual(self.characters.exports,2)

    def test_non_v2_and_unknown_profile_blocked(self):
        for purpose in ('admin','default'):
            with self.assertRaisesRegex(ValueError,'select a registered v2'):
                self.owner.select_profile('not_registered',purpose)
        with self.assertRaisesRegex(ValueError,'purpose'):
            self.owner.select_profile('human_female','unexpected')


if __name__ == '__main__': unittest.main()
