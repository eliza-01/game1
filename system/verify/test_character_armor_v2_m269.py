"""Armor v2 contracts: deferred authoring, gender overrides, identity reuse and runtime."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'control-center'))
from character_store import CharacterStore
from character_core.components import CharacterComponents
from character_core.part_names import parse_part
from character_core.armor import ArmorCatalog
from character_core.assemblies import CharacterAssemblies
from sqlite_connection import connect

IDENTITY=[1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.]


class ArmorV2Tests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.source=self.root/'source.fbx';self.source.write_bytes(b'fbx fixture')
        self.bones=[dict(name='root',parent='',matrix=IDENTITY)]
        self.parts=['human_common_m001_upper','human_male_m002_upper','human_female_m002_upper',
                    'human_common_m001_boots','human_male_m001_head','human_female_m001_head',
                    'human_male_m001_eye_l','human_male_m001_eye_r',
                    'human_male_m001_eyebrow_l','human_male_m001_eyebrow_r',
                    'human_male_m001_hair']
        def analyzer(root,source,output=None):
            if output:
                Path(output).mkdir(parents=True,exist_ok=True)
                for name in ['rig',*self.parts]:(Path(output)/(name+'.fbx')).write_bytes(name.encode())
            return dict(armature='human_armature',bones=copy.deepcopy(self.bones),parts=[
                dict(name=n,vertices=3,triangles=1,content_sha256=n+'hash',armature='human_armature',
                     skeleton=copy.deepcopy(self.bones),used_bones=['root']) for n in self.parts])
        self.characters=CharacterStore(self.root)
        self.components=CharacterComponents(self.root,analyzer=analyzer)
        inspected=self.components.inspect(self.source)
        self.components.register(inspected['token'],[],compatibility={
            'human_common_m001_upper':['male','female'],'human_male_m002_upper':['male'],
            'human_female_m002_upper':['female']})
        with connect(self.components.db) as db:
            db.execute("UPDATE character_component_records SET model_asset_id='123456',published_revision=revision")
        self.armor=ArmorCatalog(self.components)
        self.assemblies=CharacterAssemblies(self.root,self.characters,self.components,self.armor)

    def atlas(self,name='human_t001_upper'):
        file=self.root/(name+'_8x8_atlas.png')
        Image.new('RGBA',(8,8),(22,33,44,255)).save(file)
        row=self.components.atlases.register_file(file,domain='character')
        with self.components.atlases.connect() as db:
            db.execute('UPDATE texture_atlas_variants SET published_id=?,published_sha256=source_sha256 WHERE id=?',
                       ('987654',row['id']))
        return row['id']

    def register_set(self,key='starter',slots=('upper',)):
        self.armor.save_set(dict(id=key,displayName=key.title(),armorType='light',expectedRevision=0))
        for slot in slots:self.armor.add_piece(dict(setId=key,slot=slot))

    def test_geometry_identity_not_equipment_set(self):
        meta=parse_part('human_male_m002_upper')
        self.assertEqual(meta['mesh_family_id'],'human_male_m002')
        self.assertEqual(meta['set_id'],'')
        with self.assertRaises(ValueError):parse_part('newborn_upper')
        self.assertEqual(self.components.snapshot()['schema_version'],2)
        self.assertEqual(self.components.snapshot()['items'][0]['kind'],'rig')
        self.assertFalse(self.components.snapshot().get('sets'))

    def test_mesh_family_catalog_and_face_pair_rules(self):
        snapshot=self.components.snapshot()
        self.assertIn({'id':'human_common_m001','rig_profile_id':'human','created_at':snapshot['mesh_families'][0]['created_at']},
                      snapshot['mesh_families'])
        for name,slot in [('human_male_m001_eye_l','eye_l'),('human_male_m001_eye_r','eye_r'),
                          ('human_male_m001_eyebrow_l','eyebrow_l'),('human_male_m001_eyebrow_r','eyebrow_r')]:
            self.assertEqual(parse_part(name)['slot'],slot)
            self.assertEqual(self.components.get('part',name)['mesh_family_id'],'human_male_m001')
        for rejected in ('eyes_01','eyes_01_l','eyebrows_01','head_01_male'):
            with self.assertRaises(ValueError):parse_part(rejected)

    def test_deferred_pieces_optional_and_gender_overrides(self):
        self.register_set('starter',('upper',))
        self.assertEqual(self.armor.resolve('starter','male','human')[1],['upper: assign mesh and texture for male'])
        atlas=self.atlas()
        self.armor.set_variant(dict(pieceId='starter_upper',gender='unisex',meshPartId='human_common_m001_upper',
                                    atlasVariantId=atlas,expectedRevision=0))
        male,errors=self.armor.resolve('starter','male','human')
        female,errors2=self.armor.resolve('starter','female','human')
        self.assertFalse(errors);self.assertFalse(errors2)
        self.assertEqual(male['upper'][0]['id'],'human_common_m001_upper')
        self.assertEqual(female['upper'][0]['id'],'human_common_m001_upper')
        self.armor.set_variant(dict(pieceId='starter_upper',gender='male',meshPartId='human_male_m002_upper',
                                    atlasVariantId=atlas,expectedRevision=0))
        self.assertEqual(self.armor.resolve('starter','male','human')[0]['upper'][0]['id'],'human_male_m002_upper')
        self.assertEqual(self.armor.resolve('starter','female','human')[0]['upper'][0]['id'],'human_common_m001_upper')
        self.assertNotIn('boots',self.armor.resolve('starter','male','human')[0])

    def test_reuse_no_republication_and_gender_rejection(self):
        atlas=self.atlas()
        for set_id in ('starter','leather'):
            self.register_set(set_id)
            self.armor.set_variant(dict(pieceId=set_id+'_upper',gender='unisex',
                meshPartId='human_common_m001_upper',atlasVariantId=atlas,expectedRevision=0))
        snapshot=self.armor.snapshot()
        self.assertEqual(len(snapshot['appearances']),1)
        for set_id in ('starter','leather'):
            self.assertEqual(self.armor.resolve(set_id,'female','human')[0]['upper'][0]['model_asset_id'],'123456')
        before=self.components.get('part','human_common_m001_upper')['revision']
        self.components.set_compatibility('human_common_m001_upper',['female'],['female','male'])
        self.assertEqual(before,self.components.get('part','human_common_m001_upper')['revision'])
        self.assertEqual(self.armor.resolve('starter','male','human')[0],{})
        with self.assertRaisesRegex(ValueError,'allowedGenders'):
            self.armor.set_variant(dict(pieceId='starter_upper',gender='male',meshPartId='human_common_m001_upper',
                                        atlasVariantId=atlas,expectedRevision=1))
        self.assertEqual(self.armor.resolve('starter','female','human')[0]['upper'][0]['id'],'human_common_m001_upper')

    def test_no_partial_write_on_conflicts_or_bad_atlas(self):
        self.register_set()
        before=self.armor.snapshot()
        with self.assertRaises(ValueError):self.armor.set_variant(dict(pieceId='starter_upper',gender='female',
            meshPartId='human_male_m002_upper',atlasVariantId=None,expectedRevision=0))
        with self.assertRaises(ValueError):self.armor.set_variant(dict(pieceId='starter_upper',gender='unisex',
            meshPartId=None,atlasVariantId=9999999,expectedRevision=0))
        self.assertEqual(self.armor.snapshot()['sets'],before['sets'])
        with self.assertRaises(ValueError):self.armor.add_piece(dict(setId='starter',slot='upper'))
        self.armor.remove_piece(dict(pieceId='starter_upper'))
        self.assertEqual(self.armor.snapshot()['sets'][0]['pieces'],[])

    def test_character_v1_is_retired_v2_resolves_explicit_gender(self):
        self.register_set()
        atlas=self.atlas()
        self.armor.set_variant(dict(pieceId='starter_upper',gender='unisex',meshPartId='human_common_m001_upper',
                                    atlasVariantId=atlas,expectedRevision=0))
        self.assertFalse(self.assemblies.resolve(dict(schema_version=1,rig_id='human'))['ready'])
        snap=self.assemblies.save(dict(id='test_character',display_name='Test',rig_id='human',
            armor_set_id='starter',gender='male',face_parts=dict(head='human_male_m001_head',eye_l='human_male_m001_eye_l',
                           eye_r='human_male_m001_eye_r',eyebrow_r='human_male_m001_eyebrow_r'),
            face_atlases={},expected_revision=0))
        row=snap['items'][0]
        self.assertEqual(row['assembly']['schema_version'],2)
        self.assertTrue(row['assembly_resolved']['ready'],row['assembly_resolved']['missing'])
        self.assertIn('upper',row['assembly_resolved']['parts'])
        self.assertIn('eye_l',row['assembly_resolved']['parts'])
        self.assertIn('eye_r',row['assembly_resolved']['parts'])
        self.assertIn('eyebrow_r',row['assembly_resolved']['parts'])
        self.assertEqual(row['assembly_resolved']['parts']['upper']['atlas_image_id'],'987654')
        self.assertNotIn('boots',row['assembly_resolved']['parts'])
        with self.assertRaisesRegex(ValueError,'incompatible'):
            self.assemblies.save(dict(id='new_character',rig_id='human',gender='female',armor_set_id='starter',
                face_parts=dict(head='human_male_m001_head',eye_l='human_male_m001_eye_l',
                           eye_r='human_male_m001_eye_r',eyebrow_r='human_male_m001_eyebrow_r'),expected_revision=0))


if __name__=='__main__':unittest.main()
