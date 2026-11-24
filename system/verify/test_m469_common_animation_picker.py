"""M469 published source picker: cross-gender family filtering and fail-closed validation."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'control-center'))
from animation_store import AnimationStore
from sqlite_connection import connect


def bone(name, parent='', x=0):
    return {'name': name, 'parent': parent, 'matrix': [1,0,0,x,0,1,0,0,0,0,1,0,0,0,0,1]}


class CommonAnimationPickerM469(unittest.TestCase):
    def test_list_assign_replace_and_remove_without_duplicate_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            database=root/'.control-center/game1.db'
            database.parent.mkdir(parents=True)
            female=[bone('root'),bone('foot_l','root'),bone('face_mouth','root',1)]
            male=json.loads(json.dumps(female))
            male[-1]['matrix'][3]=2
            with connect(database) as db:
                db.execute('CREATE TABLE characters(id TEXT PRIMARY KEY,display_name TEXT,race TEXT,gender TEXT,skeleton_signature TEXT)')
                db.execute('CREATE TABLE character_component_records(kind TEXT,id TEXT,metadata_json TEXT)')
                for cid,race,gender,rig in [
                    ('human_female','human','female',female),
                    ('human_male','human','male',male),
                    ('elf_female','elf','female',female),
                ]:
                    db.execute('INSERT INTO characters VALUES(?,?,?,?,?)',(cid,cid,race,gender,'sig'+cid))
                    db.execute('INSERT INTO character_component_records VALUES(?,?,?)',('rig',cid,json.dumps({'bones':rig})))
            store=AnimationStore(root)

            def insert(cid,slot,asset,*,scope='base',moderation='Approved',sha='current',published='current'):
                clip=cid+'_'+scope+'_'+slot
                bid='binding_'+clip
                with store.connect() as db:
                    db.execute('''INSERT INTO animation_clips(id,character_id,name,source_path,prepared_path,sha256,
                        asset_id,published_sha256,moderation_state,revision,created_at,updated_at)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
                        (clip,cid,slot,'x.rbxm','x.rbxm',sha,asset,published,moderation,1,1,1))
                    db.execute('''INSERT INTO animation_bindings(id,character_id,scope,weapon_set,slot,variant,clip_id,weight,
                        looped,priority,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
                        (bid,cid,scope,'',slot,0,clip,100,0,'Action',1,1))
                return bid

            female_jump=insert('human_female','jump_start','124331685465753')
            male_jump=insert('human_male','jump_start','678901234')
            female_hi=insert('human_female','hi','999',scope='social')
            insert('human_female','clap','888',scope='social',moderation='Pending')
            insert('human_male','sad','777',scope='social',sha='updated',published='old')
            insert('elf_female','jump_start','555')

            candidates=store.snapshot('human_male')['sharedCandidates']
            ids={r['bindingId'] for r in candidates}
            self.assertEqual(ids,{female_jump,male_jump,female_hi})
            self.assertEqual({r['sourceGender'] for r in candidates},{'female','male'})
            jumps=[r for r in candidates if r['slot']=='jump_start']
            self.assertTrue(all(r['ready'] for r in jumps))
            incompatible=next(r for r in candidates if r['bindingId']==female_hi)
            self.assertFalse(incompatible['ready'])
            self.assertIn('bind',incompatible['reason'])
            with self.assertRaisesRegex(ValueError,'incompatible bind'):
                store.set_shared(female_hi,True)

            store.set_shared(female_jump,True)
            selected=store.snapshot('human_male')['sharedCandidates']
            self.assertTrue(next(r for r in selected if r['bindingId']==female_jump)['selected'])
            self.assertEqual(len(store.shared_rows('human')),1)
            store.set_shared(male_jump,True)
            selected=store.snapshot('human_female')['sharedCandidates']
            self.assertTrue(next(r for r in selected if r['bindingId']==male_jump)['selected'])
            self.assertEqual(len(store.shared_rows('human')),1)
            self.assertEqual(store.shared_rows('human')[0]['asset_id'],'678901234')
            store.set_shared(male_jump,False)
            self.assertEqual(store.shared_rows('human'),[])
            # Original source clips are never removed by Common assignments.
            with store.connect() as db:
                self.assertEqual(db.execute('SELECT count(*) FROM animation_clips').fetchone()[0],6)

    def test_interface_exposes_manual_list_without_new_publication_route(self):
        root=Path(__file__).resolve().parents[2]
        html=(root/'system/control-center/static/index.html').read_text(encoding='utf-8')
        js=(root/'system/control-center/static/character-animation-ui.js').read_text(encoding='utf-8')
        for element in ('animation-common-search','animation-common-select','animation-common-assign','animation-common-details'):
            self.assertIn(element,html)
        self.assertIn('data.sharedCandidates',js)
        self.assertIn('option.disabled=!row.ready',js)
        self.assertIn('setCommon(commonSelection,true)',js)
        self.assertIn("'/api/animations/shared'",js)


if __name__=='__main__':
    unittest.main()
