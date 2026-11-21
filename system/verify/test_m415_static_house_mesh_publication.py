"""M415: a detached static house part publishes without a fictitious armature.

The full-house technical carrier is still a separate, mandatory publication.
"""
from __future__ import annotations

import ast
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import sqlite3
from contextlib import contextmanager
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase, mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from real_estate.store import RealEstateStore


@contextmanager
def opened_database(path):
    # sqlite3.Connection.__exit__ commits/rolls back; it does not close.
    # Close explicitly before TemporaryDirectory cleanup on Windows.
    connection = sqlite3.connect(path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


class StaticPublicationM415(TestCase):
    def test_blender_stages_unskinned_part_without_creating_house_armature(self):
        """Execute the real Blender main() against a fake one-mesh scene."""
        path = ROOT / 'system/asset-manager/prepare_real_estate_publication_fbx.py'
        code = ast.parse(path.read_text(encoding='utf8'))
        main = next(stmt for stmt in code.body if isinstance(stmt, ast.FunctionDef) and stmt.name == 'main')
        module = compile(ast.fix_missing_locations(ast.Module(body=[main], type_ignores=[])), str(path), 'exec')

        class MeshData:
            users = 0
            vertices = []
            def copy(self): return MeshData()
        class Mesh:
            type = 'MESH'
            parent = None
            modifiers = []
            vertex_groups = []
            matrix_world = SimpleNamespace(copy=lambda: 'source-transform')
            def __init__(self, name):
                self.name, self.data = name, MeshData()
            def copy(self): return Mesh(self.name)
        source = Mesh('walls_outside')
        objects = [source]
        bpy = SimpleNamespace(
            ops=SimpleNamespace(object=SimpleNamespace(select_all=lambda **k:None, delete=lambda **k:None),
                                import_scene=SimpleNamespace(fbx=lambda **k:None)),
            context=SimpleNamespace(scene=SimpleNamespace(objects=objects, collection=SimpleNamespace(objects=SimpleNamespace(link=lambda obj:objects.append(obj))))),
            data=SimpleNamespace(objects=SimpleNamespace(remove=lambda obj, **k:objects.remove(obj)),
                                 meshes=SimpleNamespace(remove=lambda obj:None)))
        def export(output, staged, **kwargs):
            self.assertEqual([x.name for x in staged], ['walls_outside'])
            Path(output).write_bytes(b'fbx export')
        env = {'bpy':bpy,'find_mesh':lambda _b,name:next(x for x in objects if x.name.casefold() == name.casefold()),
               'find_rig':lambda *args:None,'retired':lambda name:False,
               'publication_analysis':lambda *args: self.fail('static part must not require house rig'),
               'validate_visual_weights':lambda *args: self.fail('static part must not require skeleton'),
               'publish_bones_for_mesh':lambda part:[], 'create_rig_carrier':lambda *args:self.fail('unexpected carrier'),
               'prepare_rig':lambda *args:self.fail('unexpected rig'), 'export_model': export,
               '_material':lambda *args:None, 'isolated_rig':lambda *args: nullcontext(),
               'carrier_bones':lambda *args:[], 'restore_authored_rigs':lambda *args:None, 'Path':Path}
        exec(module, env)
        with TemporaryDirectory() as tmp:
            result = env['main'](Path(tmp)/'in.fbx', Path(tmp)/'out', {}, 'walls_outside')
            self.assertEqual(result['rigAssets'], {'walls_outside':'walls_outside.fbx'})
            self.assertEqual(result['parts']['walls_outside']['status'], 'static_mesh')
        self.assertEqual(len(objects), 1)
        self.assertIs(objects[0], source)

    def test_full_house_without_armature_still_rejected(self):
        src = (ROOT/'system/asset-manager/prepare_real_estate_publication_fbx.py').read_text(encoding='utf8')
        self.assertIn("len(house_rigs) != 1 and not static_revision", src)
        self.assertIn("selected_part not in (None, 'rig_carrier')", src)

    def test_recover_missing_position_from_verified_original_source(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            path = root/'assets/house.fbx'
            path.parent.mkdir(parents=True)
            path.write_bytes(b'authored source')
            row = {'model_path':'assets/house.fbx',
                   'model_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
            fake = SimpleNamespace(root=root)
            placement = {'version':3,'centerInPivot':[15.0,2.0,-6.0], 'size':[10,10,10]}
            with mock.patch('real_estate.fbx.inspect_selected', return_value={'meshes':[
                    {'name':'walls_outside','authoredPlacement':placement}]}) as inspected:
                self.assertEqual(RealEstateStore._original_part_placement(fake,row,'walls_outside'), placement)
                inspected.assert_called_once_with(root,path,'walls_outside')
            path.write_bytes(b'mutated')
            with self.assertRaisesRegex(ValueError,'original house FBX unavailable'):
                RealEstateStore._original_part_placement(fake,row,'walls_outside')

    def test_replacing_static_mesh_keeps_original_house_space_placement(self):
        placement = {'version':3,'centerInPivot':[16,4,-3], 'size':[12,7,3]}
        old = {'name':'walls_outside','armature':'house_armature','bones':[],
               'authoredPlacement':placement}
        row = {'meshParts':['walls_outside'], 'revision':6,
               'skeleton':{'schemaVersion':1, 'meshes':[old]},
               'meshSources':{},'slug':'house_level5_01'}
        with TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); (root/'.control-center').mkdir()
            with opened_database(root/'.control-center/db.sqlite') as connection:
                connection.execute('create table real_estate (slug text primary key, skeleton_json text, mesh_sources_json text, revision integer, updated_at real)')
                connection.execute('insert into real_estate values (?,?,?,?,0)',
                                   (row['slug'], json.dumps(row['skeleton']), '{}', 6))
            fake = SimpleNamespace(root=root, get=lambda slug:row,
                                   _pending_publication_for_house=lambda slug:False,
                                   connect=lambda:opened_database(root/'.control-center/db.sqlite'),
                                   export=lambda:None)
            source = root/'new.fbx'; source.write_bytes(b'new')
            with mock.patch('real_estate.store.inspect_revision', return_value={'name':'walls_outside','bones':[], 'armature':'', 'influencedBones':[]}), mock.patch('real_estate.store.save_immutable', return_value={'path':'rev.fbx','sha256':'ab'}):
                RealEstateStore.replace_mesh(fake,row['slug'],'walls_outside',str(source),expected_revision=6)
            with opened_database(root/'.control-center/db.sqlite') as db:
                saved = json.loads(db.execute('select skeleton_json from real_estate').fetchone()[0])
            mesh = saved['meshes'][0]
            self.assertEqual(mesh['authoredPlacement'],placement)
            self.assertEqual(mesh['bones'], [])
            self.assertEqual(mesh['armature'],'')

    def test_publish_scoped_static_model_recovers_placement_and_updates_only_its_id(self):
        from real_estate.rig_publication_policy import publication_fingerprint
        with TemporaryDirectory() as tmp:
            root=Path(tmp).resolve(); (root/'.control-center').mkdir()
            (root/'original.fbx').write_bytes(b'whole house')
            (root/'standalone.fbx').write_bytes(b'standalone static wall')
            full_hash=hashlib.sha256(b'whole house').hexdigest()
            part_hash=hashlib.sha256(b'standalone static wall').hexdigest()
            current=publication_fingerprint(part_hash,carrier=False)
            carrier=publication_fingerprint(full_hash,carrier=True)
            old_rigs={'rig_carrier': {'assetId':'101', 'publishedSha256':carrier},
                      'walls_outside':{'assetId':'102','publishedSha256':'previous'}}
            original_skeleton={'schemaVersion':1,'meshes':[{'name':'walls_outside',
                'armature':'','bones':[], 'influencedBones':[]}]}
            path=root/'.control-center/estate.sqlite'
            with opened_database(path) as db:
                db.executescript("""create table real_estate (slug text primary key, skeleton_json text,
                   model_rigs_json text, model_asset_id text, model_moderation text,
                   updated_at real, model_published_hash text);
                   create table real_estate_publications (id integer primary key,house_slug text,
                   part text,asset_id text,sha256 text,operation text,published_at real);""")
                db.execute('insert into real_estate values (?,?,?,?,?,0,?)',
                    ('house_level5_01', json.dumps(original_skeleton), json.dumps(old_rigs), '101','', ''))
            placement={'version':3,'centerInPivot':[5,3,-2], 'size':[10,4,3]}
            class Stub:
                atlases=None
                def __init__(self): self.root=root
                def connect(self): return opened_database(path)
                def export(self): pass
                def _pending_publication(self,slug,part,sha): return None
                def _remember_operation(self,slug,part,sha,operation):
                    with self.connect() as db:
                        return db.execute('insert into real_estate_publications (house_slug,part,sha256,operation,asset_id,published_at) values (?,?,?,?,?,0)',
                            (slug,part,sha,operation,'')).lastrowid
                def _original_part_placement(self,row,part): return placement
                def get(self,slug):
                    with self.connect() as db:
                        record=db.execute('select skeleton_json,model_rigs_json from real_estate where slug=?',(slug,)).fetchone()
                    rigs=json.loads(record[1]); skeleton=json.loads(record[0]);
                    return {'slug':slug,'meshParts':['walls_outside'],
                        'model_path':'original.fbx','model_sha256':full_hash,
                        'meshSources':{'walls_outside':{'path':'standalone.fbx','sha256':part_hash}},
                        'rigSourceHashes':{'walls_outside':part_hash},
                        'rigPublicationHashes':{'walls_outside':current,'rig_carrier':carrier},
                        'rigAssets':rigs,'skeleton':skeleton,
                        'publicationCurrent':{'model':rigs['walls_outside']['publishedSha256']==current},
                        'meshOptions':{'walls_outside':{'appearanceMode':'material'}},
                        'textures':{'walls_outside':{'path':''}},'status':'UPDATE_AVAILABLE'}
            def stage(_root,_source,target,*args,**kwargs):
                target.mkdir(parents=True,exist_ok=True)
                (target/'walls_outside.fbx').write_bytes(b'prepared')
            with mock.patch('real_estate.store.prepare_publication',side_effect=stage), \
                 mock.patch('real_estate.store.create_model_asset',return_value='op-123') as uploaded, \
                 mock.patch('real_estate.store.wait_for_operation',return_value=SimpleNamespace(asset_id=999,moderation_state='Approved')):
                result=RealEstateStore.publish(Stub(),'house_level5_01',
                    {'creatorType':'User','creatorId':'1','apiKey':'fake'},scope='model:walls_outside')
            self.assertEqual(result['rigAssets']['walls_outside']['assetId'],'999')
            self.assertEqual(result['rigAssets']['rig_carrier']['assetId'],'101')
            self.assertEqual(result['skeleton']['meshes'][0]['authoredPlacement'],placement)
            self.assertEqual(uploaded.call_count,1)

    def test_studio_sync_validates_static_and_skinned_without_moving_carrier(self):
        studio = (ROOT/'system/studio-plugin/modules/StudioRealEstateModel.luau').read_text(encoding='utf8')
        api = (ROOT/'system/control-center/real_estate/studio_sync.py').read_text(encoding='utf8')
        self.assertIn('if standaloneStaticParts[part] == true then', studio)
        self.assertIn('PartPlacement.AlignOrigin(rig, mesh, authoredOrigin,', studio)
        self.assertIn('PartPlacement.AlignSharedPivot(rig, mesh, authoredOrigin, part)', studio)
        self.assertIn('rootCarrier, carrierInspection = StudioRealEstateRigValidation.Verify(', studio)
        self.assertIn("'standaloneStaticParts': {", api)
        self.assertIn("mesh['name'] in row.get('meshSources', {})", api)

    def test_publication_success_is_not_optimistic_ui_success(self):
        ui = (ROOT/'system/control-center/static/real-estate.js').read_text(encoding='utf8')
        self.assertIn('latest.rigAssets[part].publishedSha256===latest.rigPublicationHashes?.[part]',ui)
        self.assertIn('Model publication finished, but current mesh revisions are not confirmed',ui)
        workflow = (ROOT/'system/control-center/static/real-estate-mesh-workflow.js').read_text(encoding='utf8')
        self.assertIn("const syncReady=current && row.status==='PUBLISHED'",workflow)
        self.assertIn('Finish publishing remaining house assets',workflow)


if __name__ == '__main__':
    import unittest
    unittest.main()
