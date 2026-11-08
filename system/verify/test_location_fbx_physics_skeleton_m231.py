"""M231: shared FBX roles, SHA-bound skeleton report and physics adapters."""
from __future__ import annotations
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services.mesh_authoring_policy import is_collision_mesh, is_glass_mesh, location_mesh_profile
from services.location_fbx_inspection import validate
from location_asset_store import LocationAssetStore


def report():
    return {'schemaVersion': 1, 'hasCollider': True,
            'armatures': ['CampfireArmature'], 'unassignedArmatures': [], 'meshes': [
                {'name': name, 'armature': 'CampfireArmature' if name == 'Visual' else '',
                 'vertices': 12, 'bones': ([{'name':'root','parent':'', 'matrixLocal':[1.0]*16}]
                     if name == 'Visual' else []),
                 'influencedBones': ['root'] if name == 'Visual' else [],
                 'role': location_mesh_profile(name, has_collider=True)['role'],
                 'physics': location_mesh_profile(name, has_collider=True)}
                for name in ('Visual', 'window_Glass', 'col_mesh')]}


class LocationMeshPhysicsM231(unittest.TestCase):
    def test_name_roles_exact_contract(self):
        for value in ('col_mesh', 'COL_Floor', 'tree_col_01', 'house_col'):
            self.assertTrue(is_collision_mesh(value), value)
        for value in ('color', 'collision', 'collar', 'mesh_glass', 'Glass'):
            self.assertFalse(is_collision_mesh(value), value)
        self.assertTrue(is_glass_mesh('window_Frames_GLASS'))
        self.assertFalse(is_glass_mesh('COL_Glass'))

    def test_collider_becomes_box_and_visual_glass_pass_through(self):
        policy = location_mesh_profile('col_mesh', has_collider=True)
        self.assertEqual((policy['canCollide'],policy['canQuery'],policy['canTouch'],policy['doubleSided'],policy['collisionFidelity']),
                         (True,True,False,False,'PreciseConvexDecomposition'))
        self.assertTrue(policy['physicsOnly'])
        for name in ('Visual', 'window_glass'):
            policy = location_mesh_profile(name, has_collider=True)
            self.assertEqual((policy['canCollide'],policy['canQuery'],policy['canTouch'],policy['doubleSided'],policy['collisionFidelity']),
                             (False,False,False,False,'Box'))
            self.assertFalse(policy['physicsOnly'])
        glass = location_mesh_profile('glass', has_collider=False)
        self.assertEqual((glass['canCollide'],glass['collisionFidelity']), (True,'PreciseConvexDecomposition'))
        no_collider = location_mesh_profile('trunk', has_collider=False)
        self.assertIsNone(no_collider['canCollide'])

    def test_shared_blender_skeleton_reader(self):
        reader = (ROOT / 'system/asset-manager/fbx_mesh_inspection.py').read_text('utf-8')
        estate = (ROOT / 'system/asset-manager/analyze_real_estate_fbx.py').read_text('utf-8')
        location = (ROOT / 'system/asset-manager/analyze_model_fbx.py').read_text('utf-8')
        for source in (estate, location):
            self.assertIn('from fbx_mesh_inspection import describe_mesh', source)
            self.assertIn('describe_mesh(bpy, mesh, rig', source)
        self.assertIn('matrixLocal', reader)
        self.assertIn('influencedBones', reader)

    def test_validator_rejects_corrupt_roles_or_bones(self):
        self.assertEqual(validate(report())['schemaVersion'], 1)
        modified = report(); modified['meshes'][1]['physics']['canCollide'] = True
        with self.assertRaisesRegex(ValueError, 'physics policy mismatch'):
            validate(modified)
        modified = report(); modified['meshes'][0]['bones'][0]['matrixLocal'] = [1.0]
        with self.assertRaisesRegex(ValueError, 'rest matrix'):
            validate(modified)

    def test_registration_inspects_before_writing_and_binds_sha(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root/'campfire.fbx'; source.write_bytes(b'fake-fbx-stub')
            atlas = root/'campfire_64x64_atlas.png'
            Image.new('RGBA',(64,64),(30,60,90,255)).save(atlas)
            store = LocationAssetStore(root)
            with mock.patch('location_asset_store.inspect_location_fbx', return_value=report()) as inspector:
                row = store.register({'nameEn':'Campfire','category':'prop',
                                      'modelSourcePath':str(source),'textureSourcePath':str(atlas),
                                      'inspectFbx':True})
            inspector.assert_called_once()
            self.assertEqual(len(row['fbxAnalysis']['meshes']), 3)
            persisted = store._analysis_path(row['slug'])
            self.assertTrue(persisted.is_file())
            self.assertEqual(json.loads(persisted.read_text('utf-8'))['sourceSha256'],row['model_sha256'])
            # Renamed source without a matching report may not reuse skeleton data.
            with store.connect() as db:
                db.execute('UPDATE location_assets SET model_sha256=? WHERE slug=?',('newhash',row['slug']))
            self.assertIsNone(store.get(row['slug'])['fbxAnalysis'])

    def test_old_registration_can_inspect_without_revision_change(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp);source=root/'tree.fbx';source.write_bytes(b'legacy-fbx')
            atlas=root/'tree_64x64_atlas.png';Image.new('RGB',(64,64)).save(atlas)
            store=LocationAssetStore(root)
            row=store.register({'nameEn':'Tree','category':'tree',
                'modelSourcePath':str(source),'textureSourcePath':str(atlas)})
            self.assertIsNone(row['fbxAnalysis'])
            with mock.patch('location_asset_store.inspect_location_fbx',return_value=report()):
                refreshed=store.inspect_registered_fbx('tree')
            self.assertEqual(refreshed['revision'], row['revision'])
            self.assertEqual(refreshed['fbxAnalysis']['armatures'], ['CampfireArmature'])

    def test_shared_runtime_studio_physics_and_scoped_sync(self):
        core = (ROOT/'src/shared/world/MeshPhysicsCore.luau').read_text('utf-8')
        plugin = (ROOT/'system/studio-plugin/plugin.project.json').read_text('utf-8')
        estate = (ROOT/'system/studio-plugin/modules/StudioRealEstateCollisionPolicy.luau').read_text('utf-8')
        loader = (ROOT/'system/studio-plugin/modules/DecoAssetLoader.luau').read_text('utf-8')
        placement = (ROOT/'system/studio-plugin/modules/DecoAssetPreparation.luau').read_text('utf-8')
        runtime = (ROOT/'src/server/world/EnvironmentAssetService.luau').read_text('utf-8')
        self.assertIn('modules.StudioMeshPhysicsCore',plugin) if False else self.assertIn('src/shared/world/MeshPhysicsCore.luau',plugin)
        self.assertIn('Core.Apply(mesh, not noCollide, fidelity,',estate)
        self.assertIn('MeshPhysics.ApplyLocationModel(model, nil, row.meshOptions)',loader)
        self.assertIn('MeshPhysics.ApplyLocationModel(model, nil, meshOptions)',placement)
        self.assertIn('MeshPhysics.ApplyLocationModelRuntime(model, nil, definition.meshOptions)',runtime)
        self.assertIn('MeshPhysics.ApplyLocationModelRuntime(cursor, nil, definitionsByModel[cursor].meshOptions)',runtime)
        self.assertNotIn('descendant.CanQuery = true',runtime)
        self.assertIn('Core.Apply(mesh, not noCollide, fidelity, doublesided)',core)
        self.assertIn('Core.CaptureLocationModel', core)
        self.assertIn('Core.RestoreLocationModel', core)
        self.assertIn('elseif noCollide then "Box"',core)
        sync = (ROOT/'system/studio-plugin/modules/DecoPlacedAssetSync.luau').read_text('utf-8')
        self.assertIn('Physics.ApplyLocationModel(model, allowedNames, row.meshOptions)',sync)
        self.assertIn('Physics.RestoreLocationModel(item.physicsBefore)',sync)
        self.assertIn('function DecoPlacedAssetSync.RefreshIds(',sync)
        self.assertNotIn('previous:Destroy()',sync)

if __name__=='__main__': unittest.main()
