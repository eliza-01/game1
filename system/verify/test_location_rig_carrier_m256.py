"""M256: Location rig authoring, immutable manifest and fail-closed migration contract.

Static checks cannot substitute for Roblox Studio skinning/Undo/Play or Open Cloud.
"""
from __future__ import annotations

import contextlib
import importlib.util
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase, mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/asset-manager'))
sys.path.insert(0, str(ROOT / 'system/control-center'))
from location_rig_contract import validate
from location_asset_store import LocationAssetStore


def bones():
    identity = [1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]
    return [{'name':'base','parent':'','matrix':identity},
            {'name':'leaf','parent':'base','matrix':identity}]


def parts():
    return [{'name':'rig_carrier','vertices':6},
            {'name':'canopy','vertices':1200},
            {'name':'wood','vertices':360},
            {'name':'col_mesh','vertices':66}]


class RigContractM256(TestCase):
    def test_deterministic_multipart_manifest(self):
        original = validate(parts(), bones())
        self.assertEqual(original['schemaVersion'],2)
        self.assertEqual([p['role'] for p in original['parts']],
                         ['visual','collider','rig_carrier','visual'])
        self.assertEqual(original['structuralHash'], validate(parts()[::-1],bones()[::-1])['structuralHash'])
        self.assertEqual(len(original['structuralHash']),64)
        self.assertNotIn('meshId',original['parts'][0])  # never invent Roblox Mesh IDs

    def test_rejects_missing_fake_or_duplicated_carrier(self):
        bads=[parts()[1:],parts()+[{'name':'rig_carrier','vertices':3}],
              [{'name':'rig_carrier','vertices':0}]+parts()[1:],
              [{'name':'RootPart','vertices':3}]+parts()]
        for bad in bads:
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                validate(bad,bones())

    def test_bone_parent_duplicate_and_cycle_fail_closed(self):
        for bad in (bones()+[bones()[0]],
                    [dict(bones()[0],parent='leaf'),bones()[1]],
                    [dict(bones()[0],matrix=[]),bones()[1]],
                    [dict(bones()[0],parent='unpublished'),bones()[1]],[]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate(parts(),bad)

    def test_real_authoring_and_publication_require_carrier(self):
        script=(ROOT/'system/asset-manager/location_rig_authoring_fbx.py').read_text('utf-8')
        pub=(ROOT/'system/asset-manager/prepare_model_publication_fbx.py').read_text('utf-8')
        helper=(ROOT/'system/asset-manager/blender_rig_carrier.py').read_text('utf-8')
        self.assertIn('from blender_rig_carrier import create_rig_carrier', script)
        self.assertIn("carrier.modifiers.new('rig_bind', 'ARMATURE')", helper)
        self.assertIn('data.from_pydata(vertices, [], faces)', helper)
        self.assertIn("if output.suffix.lower() != '.fbx' or output.exists()",script)
        self.assertIn('location_manifest(objects)',pub)
        self.assertIn("visual_skin(objects)",pub)
        self.assertIn("'locationRigManifest': published",pub)
        self.assertNotIn('add_carrier(',pub)  # publication never creates hidden fallback

    def test_manifest_survives_model_publication_and_slug_rename(self):
        from PIL import Image
        with TemporaryDirectory() as folder:
            root=Path(folder)
            picture=root/'fence_32x32_atlas.png'
            Image.new('RGBA',(32,32),(1,2,3,255)).save(picture)
            fbx=root/'fence.fbx';fbx.write_bytes(b'authored real rig reference')
            store=LocationAssetStore(root)
            row=store.register({'slug':'fence','nameEn':'Fence','category':'fence',
                                'textureSourcePath':str(picture),'modelSourcePath':str(fbx)})
            self.assertIsNone(store.rig_manifest('fence','98321'))
            manifest=validate(parts(),bones())
            @contextlib.contextmanager
            def fake_stage(*args,**kwargs):
                self.assertEqual(kwargs['texture_mode'],'geometry_only')
                kwargs['report_receiver'].update({'locationRigManifest':manifest})
                yield fbx
            response=SimpleNamespace(asset_id='98321',moderation_state='Approved',operation_path='op/1')
            with mock.patch('location_asset_store.staged_model',fake_stage),\
                 mock.patch('location_asset_store.create_model_asset',return_value='op/1'),\
                 mock.patch('location_asset_store.wait_for_operation',return_value=response):
                published=store.publish('fence',{'apiKey':'dummy'},scope='model')
            self.assertEqual(published['model_asset_id'],'98321')
            self.assertEqual(store.rig_manifest('fence','98321')['structuralHash'],manifest['structuralHash'])
            with store.connect() as db:
                self.assertEqual(db.execute('SELECT count(*) FROM location_asset_publications').fetchone()[0],1)
            renamed=store.rename_identity('fence',{'slug':'old_fence','nameEn':'Old Fence',
                'category':'fence','destructible':False,'expectedRevision':row['revision']})
            self.assertEqual(renamed['model_asset_id'],'98321')
            self.assertEqual(store.rig_manifest('old_fence','98321')['structuralHash'],manifest['structuralHash'])
            self.assertEqual(store.model_publication_ids('old_fence'),['98321'])
            self.assertEqual(store.atlases.binding('location_asset','old_fence')['variant_id'],row['atlasVariantId'])

    def test_legacy_root_requires_new_fbx_publication_not_skeleton_repair(self):
        plugin=ROOT/'system/studio-plugin/modules'
        carrier=(plugin/'StudioLocationRigCarrier.luau').read_text('utf-8')
        inventory=(plugin/'StudioPlaceRegistryInventory.luau').read_text('utf-8')
        repair=(plugin/'StudioPlaceRegistryRepair.luau').read_text('utf-8')
        sync=(plugin/'StudioPlaceRegistrySync.luau').read_text('utf-8')
        self.assertFalse((plugin/'StudioLocationCarrierMigration.luau').exists())
        self.assertIn('CarrierRig.Diagnose',inventory)
        self.assertIn('требуется перепубликация FBX',inventory)
        self.assertIn('Импортный RootPart — требуется перепубликация FBX',repair)
        self.assertNotIn('CarrierMigration',repair)
        self.assertNotIn('plan.source:Clone()',repair)
        self.assertIn('if not ref.row.canSync or not ref.root then',sync)
        self.assertIn('not Carrier.IsCarrier(child)',sync)
        self.assertIn('Bone outside published rig_carrier',carrier)

    def test_read_only_audit_all_registered_assets(self):
        spec=importlib.util.spec_from_file_location('m256_audit',ROOT/'system/asset-manager/audit_location_rig_migration.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        with TemporaryDirectory() as folder:
            root=Path(folder)
            store=LocationAssetStore(root)
            with store.connect() as db:
                db.execute('INSERT INTO location_assets(slug,name_en,category,created_at,updated_at)'
                           " VALUES('fence','Fence','fence',1,1)")
            before=(root/'.control-center/game1.db').read_bytes()
            report=mod.audit(root)
            after=(root/'.control-center/game1.db').read_bytes()
            self.assertEqual(before,after)
            self.assertEqual(report['totalRegistered'],1)
            self.assertEqual(report['items'][0]['status'],'source_missing')
            self.assertTrue(report['readOnly'])
