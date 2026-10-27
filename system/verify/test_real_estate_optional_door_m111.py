"""M111: absent door is a supported Real Estate topology throughout publishing."""
from __future__ import annotations
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from real_estate.contracts import validate_analysis, present_parts, warnings_for_analysis
from real_estate.store import RealEstateStore
from real_estate.studio_sync import RealEstateStudioSync
from real_estate import fbx
from test_real_estate_m107 import skeleton


def house_only():
    return {'schemaVersion': 1, 'meshes': [json.loads(json.dumps(skeleton()['meshes'][0]))]}


class OptionalDoorContracts(unittest.TestCase):
    def test_house_armature_is_required_but_door_and_bones_are_not(self):
        record = house_only()
        record['meshes'][0].update(armature='', bones=[], influencedBones=[])
        with self.assertRaisesRegex(ValueError,'house_armature'):
            validate_analysis(record)
        self.assertTrue(any(w['code']=='missing_house_armature' for w in warnings_for_analysis(record)))
        record['meshes'][0]['armature'] = 'house_armature'
        self.assertEqual(present_parts(validate_analysis(record)), ('house',))
        self.assertIn('missing_door',{w['code'] for w in warnings_for_analysis(record)})
        for meshes in [[], skeleton()['meshes'][1:], record['meshes']*2]:
            with self.subTest(meshes=meshes), self.assertRaises(ValueError):
                validate_analysis({'meshes':meshes})

    def test_preserve_existing_two_rigs_and_validate_single_rig(self):
        self.assertEqual(present_parts(validate_analysis(skeleton())), ('house','door'))
        from real_estate.contracts import assert_rig_survived
        assert_rig_survived(house_only(), house_only(), 'house')
        with self.assertRaises(ValueError):
            assert_rig_survived(house_only(), {'meshes':[skeleton()['meshes'][1]]}, 'house')


class OptionalDoorPublication(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix='m111-house-only-')
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        incoming=self.root/'incoming'; incoming.mkdir()
        self.source=incoming/'house_level2_01.fbx'; self.source.write_bytes(b'FBX')
        self.texture=incoming/'house.png'; self.texture.write_bytes(b'PNG')
        self.store=RealEstateStore(self.root)
        self.register({'sourcePath':str(self.source),'houseType':'house','level':2,'variant':'01',
                       'textures':{'house':str(self.texture)},'acceptWarnings':True})
        self.calls=[]
        self.assetids=iter([90001,90002,90003,90004])

    def register(self, payload, *, analysis=None):
        with patch('real_estate.store.inspect', return_value=analysis or house_only()):
            return self.store.register(payload)

    def publish(self, scope='all'):
        def stage(root, source, destination, expected, images):
            self.assertEqual(set(images), set(present_parts(expected)))
            destination.mkdir()
            for part in present_parts(expected):
                (destination/f'{part}.fbx').write_bytes(part.encode())
        def create_model(path, **kwargs):
            self.calls.append('model:'+path.stem)
            return 'operations/'+path.stem
        def create_image(path, **kwargs):
            self.calls.append('image:'+kwargs['display_name'].split()[-1])
            return 'operations/image'
        creds={'apiKey':'test','creatorType':'user','creatorId':'1'}
        with patch('real_estate.store.prepare_publication',side_effect=stage), \
             patch('real_estate.store.prepare_texture',side_effect=lambda root,part,source,dest: source), \
             patch('real_estate.store.create_model_asset',side_effect=create_model), \
             patch('real_estate.store.create_image_asset',side_effect=create_image), \
             patch('real_estate.store.wait_for_operation',side_effect=lambda operation,**kw:
                  SimpleNamespace(asset_id=next(self.assetids),moderation_state='Approved')):
            return self.store.publish('house_level2_01',creds,scope=scope)

    def test_registration_publish_retry_and_studio_sync_have_no_phantom_door(self):
        row=self.store.get('house_level2_01')
        self.assertEqual(row['meshParts'],['house'])
        self.assertEqual(set(row['textures']),{'house'})
        with self.assertRaisesRegex(ValueError, 'absent'):
            self.publish('door')
        row=self.publish()
        self.assertEqual(self.calls,['model:house','image:house'])
        self.assertEqual(row['status'],'PUBLISHED')
        self.assertEqual(row['publicationCurrent'],{'model':True,'house':True})
        self.assertEqual(set(row['rigAssets']),{'house'})
        self.calls.clear(); self.publish()
        self.assertEqual(self.calls,[])
        self.assertEqual({entry['part'] for entry in self.store.publications(row['slug'])},
                         {'model:house','house'})
        observed=[]
        def load(*args,**kwargs):
            observed.append(kwargs['metadata'])
            return {'realEstateStats':{'bonesValidated':True,'rigsValidated':1,'texturesApplied':1}}
        RealEstateStudioSync(self.store,load).sync(row['slug'])
        self.assertEqual(observed[0]['doorModelAssetId'],'')
        self.assertEqual(set(observed[0]['expectedMeshes']),{'house'})
        self.assertEqual([t['slot'] for t in observed[0]['textures']],['house'])

    def test_replacing_two_rig_fbx_with_house_only_discards_stale_active_door(self):
        # Previously published door IDs remain in historical rows but can no
        # longer cause a phantom DoorRig to be loaded or a door image to appear.
        previous = self.store.get('house_level2_01')
        with self.store.connect() as db:
            db.execute('UPDATE real_estate SET model_rigs_json=? WHERE slug=?',
                 (json.dumps({'door':{'assetId':'88888','publishedSha256':'old'}}),previous['slug']))
            old = {'door':{'assetId':'77777','publishedSha256':'old',
                            'path':'assets/old.png','sha256':'old'}}
            db.execute('UPDATE real_estate SET textures_json=? WHERE slug=?',
                 (json.dumps({**previous['textures'],**old}),previous['slug']))
        row=self.store.get(previous['slug'])
        self.assertEqual(row['meshParts'],['house'])
        self.assertNotIn('door',row['rigAssets'])
        self.assertNotIn('door',row['textures'])
        self.assertFalse(any(t['reference'].endswith(':door') for t in self.store.texture_references()))

    def test_house_texture_only_can_be_replaced_without_model_publication(self):
        self.publish()
        new=self.root/'replacement.png';new.write_bytes(b'new texture')
        edit={'existingSlug':'house_level2_01','sourcePath':'', 'houseType':'house',
              'level':2,'variant':'01','textures':{'house':str(new)}}
        row=self.register(edit)
        self.assertTrue(row['publicationCurrent']['model'])
        self.assertFalse(row['publicationCurrent']['house'])
        self.calls.clear();self.publish('house')
        self.assertEqual(self.calls,['image:house'])


class BlenderErrorReporting(unittest.TestCase):
    def test_python_script_failure_cannot_be_masked_by_exit_zero(self):
        with tempfile.TemporaryDirectory(prefix='m111-blender-') as tmp:
            source=Path(tmp)/'house.fbx';source.write_bytes(b'FBX')
            with patch('real_estate.fbx.blender_executable',return_value=Path('blender')), \
                 patch('real_estate.fbx.subprocess.run',return_value=SimpleNamespace(
                     returncode=0,stdout="RuntimeError: house is missing",stderr='')) as running:
                with self.assertRaisesRegex(ValueError,'house is missing'):
                    fbx.inspect(Path(tmp),source)
                args=running.call_args[0][0]
                self.assertEqual(args[args.index('--python-exit-code')+1],'1')

    def test_analyzer_and_exporter_only_iterate_meshes_that_exist(self):
        analyze=(ROOT/'system/asset-manager/analyze_real_estate_fbx.py').read_text()
        prepare=(ROOT/'system/asset-manager/prepare_real_estate_publication_fbx.py').read_text()
        plugin=(ROOT/'system/studio-plugin/modules/StudioRealEstateModel.luau').read_text()
        js=(ROOT/'system/control-center/static/real-estate.js').read_text()
        self.assertIn("for name in expected:",analyze)
        self.assertIn('for part in parts:',prepare)
        self.assertIn('for _, part in parts do',plugin)
        self.assertIn('rigsValidated = #parts',plugin)
        self.assertIn('parts.map(part=>',js)
        self.assertIn('textureReferences:Object.fromEntries(parts.filter(part=>!realEstateIsCollider(part)).map(',js)


if __name__=='__main__':unittest.main()
