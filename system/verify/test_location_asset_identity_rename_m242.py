"""M242: rename published Location metadata without losing Roblox/Atlas identities."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sys
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'system/control-center'))
from location_asset_store import LocationAssetStore
from services.place_registry.catalog import build_catalog
from api.write_world import route as write_route


class LocationAssetIdentityRenameM242(TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.store=LocationAssetStore(self.root)
        with self.store.connect() as db:
            db.execute("""INSERT INTO location_assets
                (slug,name_en,category,model_path,model_sha256,model_asset_id,
                 model_published_sha256,destructible,revision,created_at,updated_at)
                VALUES('old_pillar','Old Pillar','fence','assets/source/location-assets/fence/old_pillar/model/old_pillar.fbx',
                'sha123','9981','sha123',0,3,1,1)""")
            db.execute("""INSERT INTO location_asset_publications
                (asset_slug,kind,revision,asset_id,operation_path,sha256,published_at)
                VALUES ('old_pillar','model',1,'771','asset-operation','sha0',1)""")
            db.execute("""INSERT INTO location_asset_mesh_id_inventory
                (asset_slug,model_asset_id,meshes_json,observed_at) VALUES(?,?,?,?)""",
                ('old_pillar','771',json.dumps([{'meshId':'133','count':1,'visualNames':['old_pillar']}]),1))
            db.execute("""INSERT INTO location_asset_mesh_id_inventory
                (asset_slug,model_asset_id,meshes_json,observed_at) VALUES(?,?,?,?)""",
                ('old_pillar','9981',json.dumps([{'meshId':'144','count':1,'visualNames':['old_pillar']},
                                                 {'meshId':'155','count':1,'visualNames':[]}]),1))
            db.execute("""INSERT INTO texture_atlas_bindings
                (consumer_type,consumer_id,variant_id,revision,changed_at,synced_revision)
                VALUES ('location_asset','old_pillar',5,2,1,2)""")
            db.execute("""INSERT INTO texture_atlas_consumer_options
                (consumer_type,consumer_id,variant_id,added_at)
                VALUES('location_asset','old_pillar',5,1)""")
            db.execute("""INSERT INTO texture_atlas_legacy_publications
                (consumer_type,consumer_id,source_sha256,image_asset_id,imported_at)
                VALUES('location_asset','old_pillar','hash','98765',1)""")
        # A real Atlas Variant makes the asset published for the registry catalog.
        with self.store.connect() as db:
            db.execute("INSERT INTO texture_atlas_families(id,atlas_key,created_at) VALUES(1,'stone',1)")
            db.execute("""INSERT INTO texture_atlas_variants
                (id,family_id,width,height,filename,original_filename,source_path,
                source_sha256,uses_alpha,published_id,published_sha256,created_at)
                VALUES(5,1,256,256,'stone_256x256_atlas.png','stone_256x256_atlas.png','unused.png',
                'hash',0,'98765','hash',1)""")
        source=self.root/'assets/manifests/location-assets-fbx/old_pillar.json'
        source.parent.mkdir(parents=True,exist_ok=True)
        source.write_text(json.dumps({'schemaVersion':1,'slug':'old_pillar',
            'sourceSha256':'sha123','analysis':{'meshes':[{'name':'old_pillar'}]}}))

    @staticmethod
    def payload(slug,revision=3):
        return {'slug':slug,'nameEn':'Stone Fence Pillar 01','category':'fence',
                'destructible':False,'expectedRevision':revision}

    def test_published_ids_and_atlas_binding_move_together_with_aliases(self):
        result=self.store.rename_identity('old_pillar',self.payload('stone_fence_pillar_01'))
        self.assertEqual((result['slug'],result['name_en'],result['model_asset_id']),
                         ('stone_fence_pillar_01','Stone Fence Pillar 01','9981'))
        self.assertEqual(result['fbxAnalysis']['meshes'][0]['name'],'old_pillar')
        self.assertEqual(result['texture_asset_id'],'98765')
        self.assertEqual(self.store.aliases_for('stone_fence_pillar_01'),['old_pillar'])
        self.assertEqual(self.store.model_publication_ids('stone_fence_pillar_01'),['9981','771'])
        self.assertEqual([v['modelAssetId'] for v in self.store.mesh_id_inventory('stone_fence_pillar_01')],
                         ['771','9981'])
        with self.store.connect() as db:
            binding=db.execute("SELECT * FROM texture_atlas_bindings WHERE consumer_id='stone_fence_pillar_01'").fetchone()
            self.assertEqual((binding['variant_id'],binding['revision'],binding['synced_revision']),(5,2,2))
            self.assertEqual(db.execute("SELECT COUNT(*) FROM texture_atlas_bindings WHERE consumer_id='old_pillar'").fetchone()[0],0)
            self.assertEqual(db.execute("SELECT consumer_id FROM texture_atlas_consumer_options").fetchone()[0],'stone_fence_pillar_01')
            self.assertEqual(db.execute("SELECT consumer_id FROM texture_atlas_legacy_publications").fetchone()[0],'stone_fence_pillar_01')
        self.assertTrue((self.root/result['identityBackup']).exists())
        catalog=build_catalog(self.store)
        item=next(v for v in catalog['items'] if v['slug']=='stone_fence_pillar_01')
        self.assertEqual(item['aliases'],['old_pillar'])
        self.assertEqual(item['models'][0]['modelAssetId'],'9981')
        self.assertEqual(item['models'][1]['meshes'][0]['meshId'],'133')
        self.assertEqual(item['atlasAssetId'],'98765')
        generated=(self.root/'src/shared/world/LocationAssetRegistry.luau').read_text()
        self.assertIn('aliases = table.freeze({',generated)
        self.assertIn('["old_pillar"] = "stone_fence_pillar_01"',generated)
        with self.assertRaisesRegex(ValueError,'reserved'):
            self.store.register({'slug':'old_pillar','nameEn':'Old Pillar','createOnly':True,
                                 'category':'fence','atlasVariantId':5})

    def test_second_rename_transfers_every_alias_and_protects_previous_names(self):
        self.store.rename_identity('old_pillar',self.payload('stone_fence_pillar_01'))
        self.store.rename_identity('stone_fence_pillar_01',self.payload('final_pillar',4))
        self.assertEqual(self.store.aliases_for('final_pillar'),['old_pillar','stone_fence_pillar_01'])
        self.assertEqual(self.store.model_publication_ids('final_pillar'),['9981','771'])
        with self.assertRaisesRegex(ValueError,'reserved'):
            self.store.rename_identity('final_pillar',self.payload('old_pillar',5))

    def test_conflicting_and_stale_slugs_never_mutate_identities(self):
        with self.assertRaisesRegex(ValueError,'changed since'):
            self.store.rename_identity('old_pillar',self.payload('new_pillar',2))
        with self.assertRaisesRegex(ValueError,'collider'):
            self.store.rename_identity('old_pillar',self.payload('col_pillar'))
        with self.store.connect() as db:
            db.execute("""INSERT INTO location_assets
                (slug,name_en,category,created_at,updated_at) VALUES('taken','Taken','fence',1,1)""")
        with self.assertRaisesRegex(ValueError,'already registered'):
            self.store.rename_identity('old_pillar',self.payload('taken'))
        self.assertIsNotNone(self.store.get('old_pillar'))
        self.assertIsNone(self.store.get('new_pillar'))

    def test_shared_studio_mesh_naming_and_alias_scan_have_undo_rules(self):
        studio=ROOT/'system/studio-plugin/modules'
        names=(studio/'StudioLocationMeshNames.luau').read_text()
        loader=(studio/'DecoAssetLoader.luau').read_text()
        repair=(studio/'StudioPlaceRegistryRepair.luau').read_text()
        scanner=(studio/'StudioPlaceRegistryInventory.luau').read_text()
        manifest=(ROOT/'system/studio-plugin/plugin.project.json').read_text()
        self.assertIn('function Naming.SingleVisual',names)
        self.assertIn('if found then return nil',names)  # multi-visual rigs keep authored names
        self.assertIn('MeshNames.Normalize(model,',loader)
        self.assertIn('MeshNames.Normalize(root,',repair)
        self.assertIn('table.insert(undo,function()',repair)
        self.assertIn('entry.aliases or {}',scanner)
        self.assertIn('meshNameMismatch',scanner)
        self.assertIn('StudioLocationMeshNames',manifest)
        runtime=(ROOT/'src/server/world/EnvironmentAssetService.luau').read_text()
        self.assertIn('LocationAssetRegistry.aliases or {}',runtime)

    def test_scoped_http_identity_endpoint(self):
        from unittest.mock import Mock
        deps={name:Mock() for name in ('deco_layouts','locations','monster_spawns',
            'npc_place_spawn','npc_register_spawn','npc_spawns','options_store',
            'publication_credentials','request_active_studio_save',
            'run_timeline_editor_bridge','sync_monster_to_studio','timelines')}
        deps['location_assets']=self.store
        status,body=write_route('/api/location-assets/old_pillar/rename-identity',
            lambda:self.payload('stone_fence_pillar_01'),deps)
        self.assertEqual(status,200)
        self.assertEqual(body['slug'],'stone_fence_pillar_01')
        status,bad=write_route('/api/location-assets/old_pillar/rename-identity',
            lambda:self.payload('other_pillar'),deps)
        self.assertEqual(status,400)
        self.assertIn('error',bad)
