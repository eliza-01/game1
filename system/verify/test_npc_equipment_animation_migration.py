"""M67 NPC equipment and animation migration integrity on isolated SQLite files."""
from pathlib import Path
import tempfile
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'control-center'))
from monster_store import MonsterStore
from monster_animation_store import MonsterAnimationStore, classify
from npc_equipment_store import NpcEquipmentStore
from npc_animation_taxonomy import filename, validate_rename

class Weapons:
    rows = [{'slug':'newbie_axe','name_en':'Newbie Axe','weapon_type':'sword','status':'PUBLISHED','model_asset_id':'123'},
            {'slug':'unpublished','name_en':'Empty','weapon_type':'bow','status':'LOCAL_ONLY','model_asset_id':''}]
    def list(self):return list(self.rows)
    def get(self,slug):return next((r for r in self.rows if r['slug']==slug),None)

class M67Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='game1-m67-')
        self.root=Path(self.temp.name)
        self.npcs=MonsterStore(self.root,kind='npc')
        with self.npcs.connect() as conn:
            conn.execute('''INSERT INTO monsters(slug,name_en,model_source_path,model_asset_id,
                   model_sha256,model_published_sha256,created_at,updated_at,skeleton_signature)
                   VALUES('generic_npc','Generic','assets/source/npcs/generic_npc/model/generic_npc.fbx','123','sha','sha',0,0,'sig')''')
        self.anim=MonsterAnimationStore(self.root,kind='npc')
        self.equip=NpcEquipmentStore(self.root,self.npcs,Weapons())
    def tearDown(self):self.temp.cleanup()

    def test_hand_loadout_validation_and_independent_export(self):
        result=self.equip.set_loadout('generic_npc','newbie_axe','newbie_axe')
        self.assertEqual(result['loadout'],{'right':'newbie_axe','left':'newbie_axe'})
        lua=(self.root/'src/shared/npc/NpcEquipmentRegistry.luau').read_text()
        self.assertIn('right = "newbie_axe"',lua)
        self.assertIn('left = "newbie_axe"',lua)
        with self.assertRaisesRegex(ValueError,'published'):
            self.equip.set_loadout('generic_npc','newbie_axe','unpublished')
        self.assertEqual(self.equip.snapshot('generic_npc')['loadout']['left'],'newbie_axe')
        self.equip.delete('generic_npc')
        self.assertEqual(self.equip.snapshot('generic_npc')['loadout']['right'],'')

    def test_subtypes_can_reuse_same_slot_variant_without_collision(self):
        inbox=self.root/'inbox';inbox.mkdir()
        for prefix in ('base','1hs','2hs'):
            (inbox/f'generic_npc_{prefix}_idle_special_01.rbxm').write_bytes(prefix.encode())
        result=self.anim.scan_folder('generic_npc',str(inbox))
        self.assertEqual(result['recognized'],3)
        self.assertEqual({r['weaponSet'] for r in self.anim.snapshot('generic_npc')['items']},{'base','1hs','2hs'})
        self.assertEqual(len({r['binding_id'] for r in self.anim.snapshot('generic_npc')['items']}),3)
        self.assertEqual(classify(Path('generic_npc_base_death.rbxm'),'generic_npc',npc=True)['weaponSet'],'base')

    def test_atomic_rename_preserves_publication_weight_disarm_and_bytes(self):
        inbox=self.root/'inbox';inbox.mkdir()
        (inbox/'generic_npc_1hs_idle_special_01.rbxm').write_bytes(b'published bytes')
        row=self.anim.scan_folder('generic_npc',str(inbox))['items'][0]
        clip=row['clipId']
        original=self.anim.snapshot('generic_npc')['items'][0]
        with self.anim.connect() as conn:
            conn.execute('UPDATE monster_animation_clips SET asset_id=?,published_sha256=sha256 WHERE id=?',('123456',clip))
        self.anim.set_weight(original['binding_id'],77)
        self.anim.set_disarm(original['binding_id'],True)
        with self.assertRaisesRegex(ValueError,'rename to generic_npc_base_idle_special_01.rbxm'):
            self.anim.rename_npc_binding(original['binding_id'],'base','badname.rbxm')
        result=self.anim.rename_npc_binding(original['binding_id'],'base','generic_npc_base_idle_special_01.rbxm')
        migrated=result['items'][0]
        self.assertEqual(migrated['clip_id'],clip)
        self.assertEqual(migrated['asset_id'],'123456')
        self.assertEqual(migrated['status'],'PUBLISHED')
        self.assertEqual(migrated['weight'],77)
        self.assertTrue(migrated['disarm'])
        self.assertEqual(migrated['weaponSet'],'base')
        self.assertEqual((self.root/migrated['source_path']).read_bytes(),b'published bytes')
        self.assertFalse((self.root/original['source_path']).exists())
        self.assertTrue((inbox/'generic_npc_base_idle_special_01.rbxm').is_file())
        self.assertFalse((inbox/'generic_npc_1hs_idle_special_01.rbxm').exists())
        rescanned=self.anim.scan_folder('generic_npc',str(inbox))
        self.assertEqual(rescanned['recognized'],1)
        self.assertEqual(len(self.anim.snapshot('generic_npc')['items']),1)
        self.assertEqual(self.anim.snapshot('generic_npc')['items'][0]['asset_id'],'123456')
        lua=(self.root/'src/shared/npc/NpcAnimationRegistry.luau').read_text()
        self.assertIn('weaponSet = "base"',lua)
        self.assertIn('disarm = true',lua)

    def test_disarm_only_special_and_bad_type(self):
        inbox=self.root/'inbox';inbox.mkdir()
        (inbox/'generic_npc_base_idle.rbxm').write_bytes(b'idle')
        binding=self.anim.scan_folder('generic_npc',str(inbox))['items'][0]['clipId']
        row=self.anim.snapshot('generic_npc')['items'][0]
        with self.assertRaisesRegex(ValueError,'only available for idle_special'):
            self.anim.set_disarm(row['binding_id'],True)
        with self.assertRaises(ValueError):
            validate_rename('foo_base_idle.rbxm','generic_npc','not_a_set','idle',0,'.rbxm')

if __name__=='__main__':unittest.main(verbosity=2)
