"""M468 shared character animation contracts, migration and bind tolerance."""
from pathlib import Path
import json
import tempfile
import unittest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'control-center'))
from animation_store import AnimationStore
from animation_core.shared import compatible_rigs
from character_core.part_names import part_bind_matches
from sqlite_connection import connect


def bone(name, parent='', x=0):
    return {'name': name, 'parent': parent, 'matrix': [1,0,0,x,0,1,0,0,0,0,1,0,0,0,0,1]}


class SharedAnimationM468(unittest.TestCase):
    def test_micro_bind_rounding_is_not_a_real_glove_conflict(self):
        female = [bone('root'), bone('hand_l','root'), bone('ring_03_l','hand_l',1)]
        male = json.loads(json.dumps(female))
        part = json.loads(json.dumps(female))
        part[2]['matrix'][3] += .0000118
        self.assertTrue(part_bind_matches(female,male,part,used_bones=['ring_03_l']))
        part[2]['matrix'][3] += .0001
        with self.assertRaisesRegex(ValueError, 'incompatible bind'):
            part_bind_matches(female,male,part,used_bones=['ring_03_l'])

    def test_cross_gender_sharing_rejects_non_locomotion_bind_differences(self):
        source = [bone('root'), bone('foot_l','root'),bone('face_mouth','root',1)]
        target = json.loads(json.dumps(source));target[-1]['matrix'][3] = 2
        self.assertEqual(compatible_rigs(source,target,scope='base',slot='jump_start'),'locomotion-core')
        with self.assertRaisesRegex(ValueError,'incompatible bind'):
            compatible_rigs(source,target,scope='social',slot='hi')
        target[1]['matrix'][3] = .01
        with self.assertRaisesRegex(ValueError,'incompatible bind'):
            compatible_rigs(source,target,scope='base',slot='jump_start')

    def test_published_share_fallback_override_unshare_and_export(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);db=root/'.control-center/game1.db';db.parent.mkdir(parents=True)
            female=[bone('root'),bone('foot_l','root'),bone('face_mouth','root',1)]
            male=json.loads(json.dumps(female));male[-1]['matrix'][3] = 2
            with connect(db) as c:
                c.execute('CREATE TABLE characters(id TEXT PRIMARY KEY, display_name TEXT,race TEXT,gender TEXT,skeleton_signature TEXT)')
                c.execute('CREATE TABLE character_component_records(kind TEXT,id TEXT,metadata_json TEXT)')
                for gender, rig in [('female',female),('male',male)]:
                    name='human_'+gender
                    c.execute('INSERT INTO characters VALUES(?,?,?,?,?)',(name,name,'human',gender,'s'+gender))
                    c.execute('INSERT INTO character_component_records VALUES(?,?,?)',('rig',name,json.dumps({'bones':rig})))
            store=AnimationStore(root)
            clip='human_female__base__jump_start__00';binding='binding__'+clip
            with store.connect() as c:
                c.execute('''INSERT INTO animation_clips(id,character_id,name,source_path,prepared_path,sha256,source_sha256,
                    asset_id,published_sha256,moderation_state,revision,created_at,updated_at,content_updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (clip,'human_female','base_jump_start','assets/source/jump.rbxm','assets/source/jump.rbxm',
                     'same','same','124331685465753','same','Approved',1,1,1,1))
                c.execute('''INSERT INTO animation_bindings(id,character_id,scope,weapon_set,slot,variant,clip_id,weight,
                    playback_speed_percent,looped,priority,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (binding,'human_female','base','','jump_start',0,clip,100,100,0,'Movement',1,1))
            store.set_shared(binding,True)
            snapshot=store.snapshot('human_male')
            self.assertEqual(snapshot['items'],[])
            self.assertEqual(len(snapshot['inherited']),1)
            self.assertEqual(snapshot['inherited'][0]['asset_id'],'124331685465753')
            self.assertIn('"shared"', (root/'assets/manifests/character-animations.json').read_text())
            luau=(root/'src/shared/character/CharacterAnimationRegistry.luau').read_text()
            self.assertIn('rbxassetid://124331685465753',luau)
            self.assertIn('family = "human"',luau)
            with store.connect() as c:
                c.execute('''INSERT INTO animation_clips(id,character_id,name,source_path,prepared_path,sha256,asset_id,published_sha256,
                    moderation_state,revision,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
                    ('male_jump','human_male','male','x.rbxm','x.rbxm','a','9','a','Approved',1,1,1))
                c.execute('''INSERT INTO animation_bindings(id,character_id,scope,weapon_set,slot,variant,clip_id,weight,looped,
                    priority,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
                    ('male_binding','human_male','base','','jump_start',0,'male_jump',100,0,'Movement',1,1))
            self.assertFalse(store.snapshot('human_male')['inherited'])
            store.delete_binding(binding)
            self.assertEqual(store.shared_rows(),[])
            self.assertFalse(store.snapshot('human_male')['shared'])

    def test_runtime_and_ui_source_references(self):
        root=Path(__file__).resolve().parents[2]
        resolver=(root/'src/client/character/animation/AnimationResolver.luau').read_text()
        self.assertIn('Registry.shared',resolver)
        self.assertIn('if type(rows) ~= "table" or #rows == 0',resolver)
        ui=(root/'system/control-center/static/index.html').read_text()
        self.assertIn('data-animation-gender="male"',ui)
        self.assertIn('data-animation-gender="female"',ui)
        self.assertIn('animation-shared-rows',ui)

if __name__=='__main__':unittest.main()
