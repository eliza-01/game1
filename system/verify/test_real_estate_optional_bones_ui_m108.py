"""M108 optional bone contracts, warnings, rig ownership and compact editor."""
from __future__ import annotations
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
sys.path.insert(0, str(ROOT / 'system/asset-manager'))
from real_estate.contracts import validate_analysis, warnings_for_analysis, assert_rig_survived
from real_estate.store import RealEstateStore
from real_estate_rig_discovery import find_rig
from test_real_estate_m107 import skeleton


class OptionalRigTests(unittest.TestCase):
    def test_bones_are_never_mandatory(self):
        src = skeleton()
        for mesh in src['meshes']:
            mesh['bones'] = []
            mesh['influencedBones'] = []
        validate_analysis(src)
        self.assertEqual({w['code'] for w in warnings_for_analysis(src)},
                         set())
        src['meshes'][1]['armature'] = ''
        validate_analysis(src)
        self.assertEqual({w['code'] for w in warnings_for_analysis(src)},
                         {'missing_door_armature'})
        for part in ('house','door'):
            assert_rig_survived(src, {'meshes':[next(x for x in src['meshes'] if x['name']==part)]}, part)

    def test_old_bone_names_do_not_generate_false_warnings(self):
        src = skeleton()
        src['meshes'][0]['bones'] = [{'name':'other', 'parent':'','matrixLocal':[1.0]*16}]
        src['meshes'][1]['bones'] = [{'name':'doot_bone','parent':'','matrixLocal':[1.0]*16}]
        validate_analysis(src)
        self.assertEqual([x['code'] for x in warnings_for_analysis(src)], [])

    def test_present_bones_still_must_survive_publication(self):
        src = skeleton()
        actual = {'meshes':[json.loads(json.dumps(src['meshes'][0]))]}
        assert_rig_survived(src,actual,'house')
        actual['meshes'][0]['bones'].pop()
        with self.assertRaisesRegex(ValueError, 'changed bone names'):
            assert_rig_survived(src,actual,'house')

    def test_inspection_and_registration_require_warning_ack_only_if_warned(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder=root/'source';folder.mkdir()
            fbx=folder/'house_level5_01.fbx';fbx.write_bytes(b'FBX')
            for filename in ('house.png','door.png'):
                (folder/filename).write_bytes(b'PNG')
            store=RealEstateStore(root)
            empty=skeleton()
            for part in empty['meshes']:
                part['bones']=[];part['influencedBones']=[]
            payload={'sourcePath':str(fbx),'houseType':'house','level':5,'variant':'01',
                     'textures':{'house':str(folder/'house.png'),'door':str(folder/'door.png')}}
            with patch('real_estate.store.inspect',return_value=empty):
                inspected=store.inspect(str(fbx))
                self.assertEqual(inspected['warnings'], [])
                # Socket features are optional. Do not require confirmation simply
                # because an older house has no chimney_bone / door_bone.
                row=store.register(payload)
            self.assertEqual(row['slug'],'house_level5_01')
            self.assertEqual(store.get(row['slug'])['rigWarnings'], [])
            self.assertEqual(store.get(row['slug'])['skeleton']['meshes'][0]['bones'],[])

    def test_armature_owner_resolved_from_links_not_naming(self):
        rig=SimpleNamespace(name='BuildingArmature', type='ARMATURE')
        mesh=SimpleNamespace(name='house', type='MESH', parent=None, modifiers=[SimpleNamespace(type='ARMATURE',object=rig)])
        fake=SimpleNamespace(context=SimpleNamespace(scene=SimpleNamespace(objects=[rig,mesh])))
        self.assertIs(find_rig(fake,mesh,'house'),rig)
        self.assertIsNone(find_rig(fake,SimpleNamespace(parent=None,modifiers=[]),'house'))

    def test_ui_is_compact_and_displays_bones_and_confirmation(self):
        js=(ROOT/'system/control-center/static/real-estate.js').read_text('utf-8')
        html=(ROOT/'system/control-center/static/index.html').read_text('utf-8')
        css=(ROOT/'system/control-center/static/real-estate.css').read_text('utf-8')
        self.assertIn('realEstateRenderRigs',js)
        self.assertIn('window.confirm',js)
        self.assertIn('acceptWarnings:',js)
        self.assertIn('<details id="real-estate-rig-details"',html)
        self.assertIn('grid-template-columns:112px minmax(0,1fr)',css)
        self.assertNotIn('must contain item_XX_bone', (ROOT/'system/control-center/real_estate/contracts.py').read_text('utf-8'))
        self.assertNotIn('or #list == 0', (ROOT/'system/studio-plugin/modules/StudioRealEstateModel.luau').read_text('utf-8'))


if __name__=='__main__':unittest.main()
