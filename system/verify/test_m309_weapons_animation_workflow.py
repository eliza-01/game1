"""M309 regressions: tested data semantics, not a simulated Roblox Studio session."""
from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'system/control-center'))
from character_store import CharacterStore
from animation_store import AnimationStore
from weapon_store import WeaponStore


class WorkflowM309(unittest.TestCase):
    def test_manual_replace_requires_exact_attestation_and_preserves_id(self):
        with tempfile.TemporaryDirectory(prefix='game1-m309-') as tmp:
            root=Path(tmp)
            characters=CharacterStore(root)
            with characters.connect() as db:
                db.execute('''INSERT INTO characters(id,display_name,source_path,prepared_path,sha256,
                  model_asset_id,status,revision,created_at,updated_at,race,gender,published_sha256,
                  publication_pipeline,bone_count) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                  ('human_female','Female','source.fbx','source.fbx','old','123456','PUBLISHED',1,
                   1,1,'human','female','old','asset',1))
            animations=AnimationStore(root)
            source=root/'new.rbxm'
            source.write_bytes(b'new animation revision')
            digest=hashlib.sha256(source.read_bytes()).hexdigest()
            with animations.connect() as db:
                db.execute('''INSERT INTO animation_clips(
                    id,character_id,name,source_path,prepared_path,sha256,source_sha256,
                    asset_id,published_sha256,moderation_state,revision,created_at,updated_at,content_updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(
                    'bow-clip','human_female','bow_walk','new.rbxm','new.rbxm',digest,digest,
                    '123456789','oldsha','Approved',2,1,1,1))
                db.execute('''INSERT INTO animation_bindings(
                    id,character_id,scope,weapon_set,slot,variant,clip_id,weight,looped,priority,
                    created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',(
                    'binding','human_female','weapon','bow','walk',0,'bow-clip',100,True,
                    'Movement',1,1))
            for args in [dict(asset_id='123456789',sha256=digest,attestation=False),
                         dict(asset_id='9999',sha256=digest,attestation=True),
                         dict(asset_id='123456789',sha256='stale',attestation=True)]:
                with self.assertRaises(ValueError):
                    animations.confirm_studio_replacement('bow-clip',**args)
            result=animations.confirm_studio_replacement('bow-clip',asset_id='123456789',sha256=digest,attestation=True)
            self.assertEqual(result['confirmation'],'USER_ATTESTED_NOT_CLOUD_VERIFIED')
            self.assertFalse(result['studioSynced'])
            item=animations.list_for_character('human_female')[0]
            self.assertEqual(item['status'],'PUBLISHED')
            self.assertEqual(item['asset_id'],'123456789')
            self.assertTrue(item['user_attested'])
            with animations.connect() as db:
                events=list(db.execute("SELECT operation_path,manual_verified FROM animation_publications"))
            self.assertEqual(len(events),1)
            self.assertIn('user-attested',events[0][0])
            self.assertEqual(events[0][1],0)
            with self.assertRaises(ValueError):
                animations.confirm_studio_replacement('bow-clip',asset_id='123456789',sha256=digest,attestation=True)
            luau=(root/'src/shared/character/CharacterAnimationRegistry.luau').read_text()
            self.assertIn('rbxassetid://123456789',luau)

    def test_weapon_type_is_explicit_metadata_change_and_no_cloud_publish(self):
        with tempfile.TemporaryDirectory(prefix='game1-m309-') as tmp:
            root=Path(tmp)
            fbx=root/'bow.fbx';fbx.write_bytes(b'mock source')
            weapons=WeaponStore(root)
            weapons.register(dict(slug='newbie_bow',nameEn='Newbie Bow',weaponType='dagger',rarity='common',modelSourcePath=str(fbx)))
            weapons.register(dict(slug='newbie_bow',nameEn='Newbie Bow',weaponType='bow',rarity='common'))
            row=weapons.get('newbie_bow')
            self.assertEqual(row['weapon_type'],'bow')
            self.assertEqual(row['model_asset_id'],None)
            self.assertTrue(row['model_source_path'])
            registry=(root/'src/shared/weapon/WeaponRegistry.luau')
            self.assertTrue(registry.exists() or len(list(root.glob('src/shared/**/*Weapon*.luau')))>0)

    def test_frontend_uses_real_shared_location_asset_editor(self):
        script=(ROOT/'system/control-center/static/weapon-workflow.js').read_text()
        self.assertIn('game1AssetWorkflowDialog',script)
        self.assertIn("game1WeaponAtlasPicker.render('weapon-workflow-atlas'",script)
        html=(ROOT/'system/control-center/static/index.html').read_text()
        self.assertIn('weapon-workflow.js?v=309',html)
        self.assertIn('weapon-register-disclosure',html)
        self.assertIn('animation-replace-manual',html)
        for file in ['weapon-workflow.js','weapon-assets.js','weapon-atlas-picker.js',
                     'asset-atlas-editor.js','character-animation-ui.js']:
            result=subprocess.run(['node','--check',str(ROOT/'system/control-center/static'/file)],
                capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()
