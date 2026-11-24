"""M470 regression: all filenames numbered, common version N maps to both sexes N."""
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
from animation_core.common import classify_animation,filename_rule_catalog,_canonical_file_stem
from sqlite_connection import connect

MIGRATION=ROOT/'system/control-center/migrations/m470_animation_versions.py'

def setup(root):
    db=root/'.control-center/game1.db';db.parent.mkdir(parents=True)
    matrix=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]
    with connect(db) as c:
        c.execute('CREATE TABLE characters(id TEXT PRIMARY KEY,display_name TEXT,race TEXT,gender TEXT,skeleton_signature TEXT,visual_mode TEXT)')
        c.execute('CREATE TABLE character_component_records(kind TEXT,id TEXT,metadata_json TEXT)')
        for g in ('male','female'):
            char='human_'+g
            c.execute('INSERT INTO characters VALUES(?,?,?,?,?,?)',(char,char,'human',g,'same','assembly'))
            c.execute('INSERT INTO character_component_records VALUES(?,?,?)',('rig',char,json.dumps({'bones':[{'name':'root','parent':'','matrix':matrix}]})))
    return AnimationStore(root)

def migrate(root):
    spec=importlib.util.spec_from_file_location('m470_version_migration',MIGRATION)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.migrate(root)

class VersionedAnimationsM470(unittest.TestCase):
    def test_all_canonical_rules_are_versioned_and_02_is_distinct(self):
        for character in ('human_male','human_female'):
            rules=filename_rule_catalog(character)
            self.assertTrue(rules)
            for rule in rules:
                self.assertTrue(rule['canonicalFilename'].endswith(('_01.rbxm','_01.rbxmx','_01.animation.json')),rule)
                self.assertEqual(rule['variantPattern'],'01..n')
                self.assertTrue(rule['variants'])
        for prefix in ('human_male','human_female','human_common'):
            for version in (1,2,3):
                result=classify_animation(Path(f'{prefix}_social_laugh_{version:02d}.rbxm'),prefix)
                self.assertEqual((result['slot'],result['variant']),('laugh',version))
            self.assertIsNone(classify_animation(Path(f'{prefix}_social_laugh.rbxm'),prefix))
        self.assertEqual((classify_animation(Path('human_common_social_waiting_01.rbxm'),'human_common')['slot'],
                          classify_animation(Path('human_common_social_sp_wait_01.rbxm'),'human_common')['slot']), ('waiting','sp_wait'))
        self.assertIsNone(classify_animation(Path('Atk02_1HS_FFighter.rbxm')))
        for value,scope,slot,version in (
            ('human_female_base_jump_start_02.rbxm','base','jump_start',2),
            ('human_female_emotions_sad_01.rbxmx','emotions','sad',1),
            ('human_male_1hs_combat_idle_02.rbxm','weapon','combat_idle',2)):
            result=classify_animation(Path(value), '_'.join(value.split('_')[:2]))
            self.assertEqual((result['scope'],result['slot'],result['variant']), (scope,slot,version))

    def test_common_02_populates_both_02_and_preserves_private_01(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);store=setup(root)
            for gender in ('male','female'):
                inbox=root/('input_'+gender);inbox.mkdir()
                (inbox/f'human_{gender}_social_laugh_01.rbxm').write_bytes(gender.encode('utf8'))
                preview=store.preview_folder('human_'+gender,str(inbox))
                self.assertEqual(preview['items'][0]['variant'],1)
                store.register_selected('human_'+gender,str(inbox),preview['items'])
            inbox=root/'common';inbox.mkdir()
            (inbox/'human_common_social_laugh_02.rbxm').write_bytes(b'common version two')
            preview=store.preview_folder('human_male',str(inbox))
            item=preview['items'][0]
            self.assertEqual((item['slot'],item['variant'],item['ownerCharacterId']),('laugh',2,'human_common'))
            self.assertEqual(store.register_selected('human_male',str(inbox),[item])['count'],1)
            with store.connect() as db:
                self.assertEqual(db.execute("SELECT count(*) FROM animation_clips WHERE character_id='human_common'").fetchone()[0],1)
                db.execute("UPDATE animation_clips SET asset_id='123456789',published_sha256=sha256,moderation_state='Approved' WHERE character_id='human_common'")
                db.execute("UPDATE animation_clips SET asset_id='123456788',published_sha256=sha256,moderation_state='Approved' WHERE character_id='human_male'")
                db.execute("UPDATE animation_clips SET asset_id='123456787',published_sha256=sha256,moderation_state='Approved' WHERE character_id='human_female'")
            store.export()
            for gender in ('male','female'):
                view=store.snapshot('human_'+gender)
                self.assertEqual([(x['slot'],x['variant'],x['asset_id']) for x in view['inherited']], [('laugh',2,'123456789')])
                self.assertEqual([(x['slot'],x['variant']) for x in view['items']], [('laugh',1)])
            lua=(root/'src/shared/character/CharacterAnimationRegistry.luau').read_text('utf8')
            self.assertIn('human_common__social__laugh__02',lua)
            self.assertIn('rbxassetid://123456789',lua)
            self.assertIn('human_male__social__laugh__01',lua)
            self.assertIn('human_female__social__laugh__01',lua)
            runtime=(ROOT/'src/shared/character/CharacterAnimationVariantMerge.luau').read_text('utf8')
            self.assertIn('keyed[version]',runtime)
            player=(ROOT/'src/client/character/animation/SocialAnimationPlayback.luau').read_text('utf8')
            self.assertIn('tonumber(version)',player)

    def test_published_legacy_clip_ids_migrate_once_without_republishing(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);store=setup(root)
            with store.connect() as db:
                for index,(scope,slot,weapon) in enumerate((('base','jump_start',''),('social','waiting_a',''),('social','sp_wait_01',''),('social','laugh',''),('weapon','combat_idle','hands'))):
                    name=_canonical_file_stem(scope,weapon,slot,0)
                    ident='human_female__'+scope+('__'+weapon if weapon else '')+'__'+slot+'__00'
                    bid='binding__'+ident
                    src='assets/source/characters/human/female/human_female/animations/'+scope+'/'+name+'.rbxm'
                    (root/src).parent.mkdir(parents=True,exist_ok=True)
                    (root/src).write_bytes(b'bytes'+bytes([index]))
                    import hashlib
                    sha=hashlib.sha256((root/src).read_bytes()).hexdigest()
                    db.execute('''INSERT INTO animation_clips(id,character_id,name,source_path,prepared_path,sha256,source_sha256,asset_id,published_sha256,moderation_state,created_at,updated_at)
                          VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',(ident,'human_female',name,src,src,sha,sha,str(710000+index),sha,'Approved',1,1))
                    db.execute('''INSERT INTO animation_bindings(id,character_id,scope,weapon_set,slot,variant,clip_id,weight,looped,priority,created_at,updated_at)
                          VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',(bid,'human_female',scope,weapon,slot,0,ident,100,0,'Action',1,1))
                    db.execute('''INSERT INTO animation_publications(clip_id,clip_revision,asset_id,operation_path,sha256,moderation_state,published_at)
                          VALUES(?,?,?,?,?,?,?)''',(ident,1,str(710000+index),'published',sha,'Approved',1))
            self.assertEqual(migrate(root),5)
            self.assertEqual(migrate(root),0)
            with store.connect() as db:
                rows=db.execute('SELECT * FROM animation_bindings').fetchall()
                self.assertEqual({row['variant'] for row in rows},{1})
                self.assertIn('waiting',{row['slot'] for row in rows})
                self.assertIn('sp_wait',{row['slot'] for row in rows})
                self.assertEqual({r[0] for r in db.execute('SELECT asset_id FROM animation_publications')},{str(710000+i) for i in range(5)})
                for clip in db.execute('SELECT * FROM animation_clips'):
                    self.assertTrue(clip['name'].endswith('_01'))
                    self.assertTrue((root/clip['source_path']).is_file())
                    self.assertEqual(clip['asset_id'],str(710000+['base_jump_start_01','social_waiting_01','social_sp_wait_01','social_laugh_01','hands_combat_idle_01'].index(clip['name'])))

if __name__=='__main__':unittest.main()
