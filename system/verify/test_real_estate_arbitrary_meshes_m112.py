"""M112: house is the only required name; other FBX meshes are first-class parts."""
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
from real_estate.contracts import validate_analysis, present_parts
from real_estate.store import RealEstateStore
from real_estate.studio_sync import RealEstateStudioSync
from real_estate.jobs import RealEstatePublicationJobs
from test_real_estate_m107 import skeleton


def many_meshes():
    data = json.loads(json.dumps(skeleton()))
    data['meshes'] += [
        {'name': part, 'armature': '', 'vertices': count,
         'bones': [], 'influencedBones': []}
        for part, count in (('repair', 24), ('stone_fence_01_kit', 80))
    ]
    return validate_analysis(data)


class ArbitraryMeshContract(unittest.TestCase):
    def test_any_extra_meshes_required_house_and_stable_order(self):
        data = many_meshes()
        self.assertEqual(present_parts(data), ('house', 'door', 'repair', 'stone_fence_01_kit'))
        self.assertEqual(present_parts({'meshes':list(reversed(data['meshes']))}), present_parts(data))
        validate_analysis({'meshes':[part for part in data['meshes'] if part['name']!='door']})
        with self.assertRaisesRegex(ValueError, 'house'):
            validate_analysis({'meshes':[part for part in data['meshes'] if part['name']!='house']})
        with self.assertRaisesRegex(ValueError, 'unique'):
            validate_analysis({'meshes':data['meshes']+[{'name':'REPAIR','vertices':8,'bones':[]}]})

    def test_blender_inspector_and_exporter_use_discovered_mesh_list(self):
        analyzer = (ROOT/'system/asset-manager/analyze_real_estate_fbx.py').read_text()
        exporter = (ROOT/'system/asset-manager/prepare_real_estate_publication_fbx.py').read_text()
        self.assertIn('for name in expected:', analyzer)
        self.assertIn("present, key=lambda name: (name != 'house'", analyzer)
        self.assertIn('for part in parts:', exporter)
        self.assertIn("for obj in bpy.context.scene.objects if obj.type == 'MESH'", exporter)
        self.assertNotIn("parts = ('house', 'door')", exporter)

    def test_browser_initial_job_status_is_safe(self):
        from shutil import which
        if not which('node'):
            self.skipTest('Node.js not available')
        script = ROOT/'system/control-center/static/real-estate.js'
        node = """const fs=require('fs'),vm=require('vm');
const source=fs.readFileSync(process.argv[1],'utf8');
const before=source.substring(0,source.indexOf('function realEstateRows()'));
const cx=vm.createContext({});vm.runInContext(before,cx);
if(cx.realEstatePublicationBusy(undefined)!==false)process.exit(3);
if(cx.realEstatePublicationBusy('house_level5_01')!==false)process.exit(4);
"""
        subprocess.run(['node','-e',node,str(script)],check=True)

    def test_studio_templates_check_each_rig_before_replacing(self):
        lua=(ROOT/'system/studio-plugin/modules/StudioRealEstateModel.luau').read_text()
        self.assertIn('local parts = orderedParts(manifests)',lua)
        self.assertIn('for _, part in parts do',lua)
        self.assertIn('pcall(function()',lua)
        self.assertIn('wrapper.Parent = destination',lua)
        self.assertLess(lua.index('verifyRig(rig, part, manifests)'),lua.index('wrapper.Parent = destination'))
        self.assertIn('Game1RigAssetIds',lua)


class ArbitraryMeshPublication(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='m112-estate-')
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        source=self.root/'author';source.mkdir()
        self.fbx=source/'house_level5_01.fbx';self.fbx.write_bytes(b'fbx data')
        self.house_image=source/'house.png';self.house_image.write_bytes(b'house texture')
        self.repair_image=source/'repair.png';self.repair_image.write_bytes(b'repair texture')
        self.store=RealEstateStore(self.root)
        with patch('real_estate.store.inspect',return_value=many_meshes()):
            self.row=self.store.register({
                'sourcePath':str(self.fbx),'houseType':'house','level':5,'variant':'01',
                'textures':{'house':str(self.house_image),'door':'',
                            'repair':'','stone_fence_01_kit':str(self.repair_image)},
                'textureReferences':{'door':'mesh:house','repair':'mesh:house'},
                'acceptWarnings':True,
            })
        self.uploads=[]
        self.counter=iter(range(45001,45100))

    def publish(self,scope='all'):
        def prepared(root,source,target,expected,images):
            self.assertEqual(tuple(images),present_parts(expected))
            target.mkdir(exist_ok=True)
            for part in present_parts(expected):
                (target/(part+'.fbx')).write_bytes(part.encode())
        def model(path,**kwargs):
            self.uploads.append('model:'+path.stem)
            return 'operations/'+path.stem
        def image(path,**kwargs):
            self.uploads.append('image:'+kwargs['display_name'].split()[-1])
            return 'operations/image'
        creds={'apiKey':'test','creatorType':'user','creatorId':'1'}
        with patch('real_estate.store.prepare_publication',side_effect=prepared),\
             patch('real_estate.store.prepare_texture',side_effect=lambda root,part,source,dest:source),\
             patch('real_estate.store.create_model_asset',side_effect=model),\
             patch('real_estate.store.create_image_asset',side_effect=image),\
             patch('real_estate.store.wait_for_operation',side_effect=lambda operation,**kw:
                 SimpleNamespace(asset_id=next(self.counter),moderation_state='Approved')):
            return self.store.publish(self.row['slug'],creds,scope=scope)

    def test_register_and_publish_all_independent_rigs_and_only_owned_images(self):
        self.assertEqual(self.row['meshParts'],['house','door','repair','stone_fence_01_kit'])
        published=self.publish()
        self.assertEqual(self.uploads,[
            'model:house','model:door','model:repair','model:stone_fence_01_kit',
            'image:house','image:stone_fence_01_kit'])
        self.assertEqual(published['status'],'PUBLISHED')
        self.assertEqual(set(published['rigAssets']),set(published['meshParts']))
        self.assertEqual(published['textures']['repair']['assetId'],published['textures']['house']['assetId'])
        self.uploads.clear();self.publish()
        self.assertEqual(self.uploads,[])
        seen=[]
        def load_model(*args,**kw):
            seen.append(kw['metadata'])
            return {'realEstateStats':{'bonesValidated':True,'rigsValidated':4,'texturesApplied':4}}
        RealEstateStudioSync(self.store,load_model).sync(self.row['slug'])
        self.assertEqual(set(seen[0]['rigAssetIds']),set(self.row['meshParts']))
        self.assertEqual([row['slot'] for row in seen[0]['textures']],self.row['meshParts'])

    def test_republish_one_arbitrary_image_and_keep_models(self):
        self.publish();self.uploads.clear()
        replacement=self.root/'new.png';replacement.write_bytes(b'updated texture')
        with patch('real_estate.store.inspect',return_value=many_meshes()):
            row=self.store.register({
                'existingSlug':self.row['slug'],'sourcePath':'',
                'houseType':'house','level':5,'variant':'01',
                'textures':{'house':self.row['textures']['house']['path'],
                            'door':'','repair':'','stone_fence_01_kit':str(replacement)},
                'textureReferences':{'door':'mesh:house','repair':'mesh:house'},
            })
        self.assertTrue(row['publicationCurrent']['model'])
        self.publish('image:stone_fence_01_kit')
        self.assertEqual(self.uploads,['image:stone_fence_01_kit'])
        self.assertEqual(self.store.get(row['slug'])['status'],'PUBLISHED')

    def test_job_scope_validates_author_part(self):
        from real_estate.jobs import RealEstatePublicationJobs
        with self.assertRaisesRegex(ValueError,'scope'):
            RealEstatePublicationJobs(self.store).start(self.row['slug'],{},scope='image:nonexistent')


if __name__=='__main__':unittest.main()
