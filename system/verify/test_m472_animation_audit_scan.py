"""M472: historical audit keys survive M470, mixed-family scan routes by prefix."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'system/control-center'))
from animation_store import AnimationStore
from sqlite_connection import connect
from services.sqlite_asset_audit_importer import SqliteAssetAuditImporter, SPECS

SCRIPT=ROOT/'system/control-center/migrations/m472_animation_audit_identity.py'


def migrate(root):
    spec=importlib.util.spec_from_file_location('m472_migration',SCRIPT)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.migrate(root)


class AnimationAuditAndMixedScanM472(unittest.TestCase):
    def test_audit_history_uses_original_key_and_new_rows_use_current(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);runtime=root/'.control-center';runtime.mkdir()
            dbfile=runtime/'game1.db';archive=runtime/'backups/m470_animation_versions_20261124T010101Z.db'
            archive.parent.mkdir()
            with connect(dbfile) as db:
                db.execute('''CREATE TABLE animation_publications (id INTEGER PRIMARY KEY,
                    clip_id TEXT,asset_id TEXT,operation_path TEXT,published_at REAL,
                    clip_revision INTEGER,sha256 TEXT,moderation_state TEXT)''')
                db.execute('INSERT INTO animation_publications VALUES(?,?,?,?,?,?,?,?)',
                           (82,'human_female__base__jump_start__00','12345678','operations/82',1,1,'a','Approved'))
            with connect(dbfile) as db, connect(archive) as backup:
                db.backup(backup)
            with connect(dbfile) as db:
                db.execute("UPDATE animation_publications SET clip_id='human_female__base__jump_start__01'")
            self.assertEqual(migrate(root)['added'],1)
            self.assertEqual(migrate(root)['added'],0)
            class Repository:
                def ensure_schema(self):pass
            importer=SqliteAssetAuditImporter(root,Repository())
            spec=next(spec for spec in SPECS if spec.domain=='character_animation')
            events=importer._events(spec)
            self.assertEqual(events[0]['assetKey'],'human_female__base__jump_start__00')
            with connect(dbfile) as db:
                db.execute('INSERT INTO animation_publications VALUES(?,?,?,?,?,?,?,?)',
                           (83,'human_common__social__laugh__02','12345679','operations/83',2,1,'b','Approved'))
            events=importer._events(spec)
            self.assertEqual(events[1]['assetKey'],'human_common__social__laugh__02')
            with connect(dbfile) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM animation_publication_audit_keys').fetchone()[0],2)
                db.execute("UPDATE animation_publication_audit_keys SET asset_id='different' WHERE publication_id=82")
            with self.assertRaisesRegex(ValueError,'provenance mismatch'):
                importer._events(spec)

    def test_missing_backup_blocks_unsafe_reconstruction(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);dbfile=root/'.control-center/game1.db';dbfile.parent.mkdir()
            with connect(dbfile) as db:
                db.execute('CREATE TABLE animation_publications(id INTEGER,clip_id TEXT,asset_id TEXT,operation_path TEXT)')
                db.execute("INSERT INTO animation_publications VALUES(1,'human_female__social__laugh__01','123','ops/1')")
            with self.assertRaisesRegex(ValueError,'m470 pre-migration backup missing'):
                migrate(root)

    def test_mixed_folder_routes_male_female_and_common_exactly_once(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);dbfile=root/'.control-center/game1.db';dbfile.parent.mkdir()
            matrix=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]
            with connect(dbfile) as db:
                db.execute('CREATE TABLE characters(id TEXT PRIMARY KEY,display_name TEXT,race TEXT,gender TEXT,skeleton_signature TEXT,visual_mode TEXT)')
                db.execute('CREATE TABLE character_component_records(kind TEXT,id TEXT,metadata_json TEXT)')
                for gender in ('male','female'):
                    char='human_'+gender
                    db.execute('INSERT INTO characters VALUES(?,?,?,?,?,?)',(char,char,'human',gender,'signature','assembly'))
                    db.execute('INSERT INTO character_component_records VALUES(?,?,?)',('rig',char,json.dumps({'bones':[{'name':'root','parent':'','matrix':matrix}]})))
            store=AnimationStore(root)
            inbox=root/'inbox';inbox.mkdir()
            filenames=['human_male_social_laugh_01.rbxm','human_female_social_laugh_01.rbxm',
                       'human_common_social_laugh_02.rbxm','elf_male_social_laugh_01.rbxm']
            for filename in filenames:(inbox/filename).write_bytes(filename.encode())
            preview=store.preview_folder('human_female',str(inbox))
            self.assertEqual(preview['recognized'],3)
            self.assertEqual(len(preview['unassigned']),1)
            self.assertEqual({row['ownerCharacterId'] for row in preview['items']},
                             {'human_male','human_female','human_common'})
            result=store.register_selected('human_female',str(inbox),preview['items'])
            self.assertEqual(result['count'],3)
            next_preview=store.preview_folder('human_male',str(inbox))
            self.assertEqual({row['status'] for row in next_preview['items']},{'UNCHANGED'})
            with store.connect() as db:
                self.assertEqual(db.execute('SELECT count(*) FROM animation_clips').fetchone()[0],3)
                self.assertEqual(db.execute('SELECT count(*) FROM animation_shared_bindings').fetchone()[0],1)
            for character in ('human_male','human_female'):
                pending=store.snapshot(character)['commonPending']
                self.assertEqual(len(pending),1)
                self.assertEqual(pending[0]['status'],'LOCAL_ONLY')
                self.assertEqual(pending[0]['character_id'],'human_common')
            with store.connect() as db:
                db.execute("UPDATE animation_clips SET asset_id='123456789',published_sha256=sha256,moderation_state='Approved' WHERE character_id='human_common'")
            self.assertEqual(store.snapshot('human_male')['commonPending'],[])
            self.assertEqual(store.snapshot('human_female')['inherited'][0]['asset_id'],'123456789')


if __name__=='__main__':unittest.main()
