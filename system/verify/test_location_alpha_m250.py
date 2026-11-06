"""M250: alpha is a per-consumer render policy, never an Atlas/Model publication."""
from __future__ import annotations

import sys
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'system/control-center'))
from location_asset_store import LocationAssetStore
from services.location_asset_alpha import validate_alpha
from services.place_registry.catalog import build_catalog,validate_report


class LocationAlphaM250(unittest.TestCase):
    def test_schema_defaults_and_idempotent_backup(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            base=root/'.control-center';base.mkdir()
            with sqlite3.connect(base/'game1.db') as db:
                db.execute('''CREATE TABLE location_assets (
                    slug TEXT PRIMARY KEY,name_en TEXT NOT NULL,category TEXT NOT NULL,
                    model_path TEXT NOT NULL DEFAULT '',model_sha256 TEXT NOT NULL DEFAULT '',
                    model_asset_id TEXT,model_published_sha256 TEXT NOT NULL DEFAULT '',
                    model_moderation_state TEXT NOT NULL DEFAULT '',destructible INTEGER NOT NULL DEFAULT 0,
                    revision INTEGER NOT NULL DEFAULT 1,created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,published_at REAL,
                    mesh_options_json TEXT NOT NULL DEFAULT '{}',
                    surface_material TEXT NOT NULL DEFAULT 'default')''')
                db.execute("INSERT INTO location_assets(slug,name_en,category,model_asset_id,created_at,updated_at) VALUES('bush_01','Bush 01','bush','123456',1,1)")
            store=LocationAssetStore(root)
            self.assertEqual(store.snapshot()['schemaVersion'],6)
            old=store.get('bush_01')
            self.assertIs(old['alphaEnabled'],False)
            self.assertEqual(old['model_asset_id'],'123456')
            backups=list((base/'backups').glob('location_alpha_m250_*.sqlite'))
            self.assertEqual(len(backups),1)
            again=LocationAssetStore(root)
            self.assertEqual(len(list((base/'backups').glob('location_alpha_m250_*.sqlite'))),1)
            self.assertFalse(again.get('bush_01')['alphaEnabled'])

    def test_alpha_toggle_never_changes_publications(self):
        with TemporaryDirectory() as tmp:
            store=LocationAssetStore(Path(tmp))
            with store.connect() as db:
                db.execute('''INSERT INTO location_assets
                    (slug,name_en,category,model_asset_id,model_published_sha256,revision,created_at,updated_at)
                    VALUES ('bush_01','Bush 01','bush','112233','abc',7,1,1)''')
            before=store.get('bush_01')
            first=store.update_alpha('bush_01',{'alphaEnabled':True,'expectedRevision':7})
            self.assertIs(first['alphaEnabled'],True)
            self.assertEqual(first['revision'],8)
            self.assertEqual(first['model_asset_id'],before['model_asset_id'])
            self.assertEqual(first['model_published_sha256'],before['model_published_sha256'])
            self.assertEqual(first['texture_asset_id'],before['texture_asset_id'])
            manifest=(Path(tmp)/'src/shared/world/LocationAssetRegistry.luau').read_text('utf8')
            self.assertIn('alphaEnabled = true',manifest)
            with self.assertRaisesRegex(ValueError,'changed since Edit'):
                store.update_alpha('bush_01',{'alphaEnabled':False,'expectedRevision':7})
            second=store.update_alpha('bush_01',{'alphaEnabled':False,'expectedRevision':8})
            self.assertIs(second['alphaEnabled'],False)
            self.assertEqual(second['revision'],9)
            self.assertEqual(store.update_alpha('bush_01',{
                'alphaEnabled':False,'expectedRevision':9})['revision'],9)

    def test_invalid_input_fails_closed(self):
        for value in (0,1,'true','false',None,[],{}):
            with self.subTest(value=value),self.assertRaises(ValueError):
                validate_alpha(value)
        with TemporaryDirectory() as tmp:
            store=LocationAssetStore(Path(tmp))
            with self.assertRaises(ValueError):
                store.update_alpha('missing',{'alphaEnabled':False,'expectedRevision':1})
            with self.assertRaises(ValueError):
                store.update_alpha('bad/slug',{'alphaEnabled':True,'expectedRevision':1})
            with self.assertRaises(ValueError):
                store.update_alpha('missing',{'alphaEnabled':True,'expectedRevision':1,'modelAssetId':'1'})

    def test_catalog_digest_is_alpha_sensitive_even_with_shared_atlas(self):
        class Fake:
            def __init__(self,enabled):self.enabled=enabled
            def snapshot(self): return {'items':[{'slug':'bush_01','status':'PUBLISHED',
                'model_asset_id':'112233','texture_asset_id':'334455',
                'alphaEnabled':self.enabled,'model_published_sha256':'sha'}]}
            def model_publication_ids(self,slug):return ['112233']
            def mesh_id_inventory(self,slug):return []
        old,new=build_catalog(Fake(False)),build_catalog(Fake(True))
        self.assertNotEqual(old['digest'],new['digest'])
        self.assertEqual(old['items'][0]['atlasAssetId'],new['items'][0]['atlasAssetId'])
        self.assertIs(new['items'][0]['alphaEnabled'],True)

    def test_report_alpha_boolean_validation_and_backward_compatibility(self):
        catalog={'items':[{'slug':'bush_01'}]}
        base=dict(schemaVersion=1,placements=[dict(key='p1',slug='bush_01',name='bush',
            path='Workspace.bush',meshId='1',textureId='2',placementId='abc',status='pending',
            needsMesh=False,needsTexture=False,needsStructure=False,duplicateId=False,
            ambiguous=False,hasModel=True,canSync=True,issues=[],transform={})])
        self.assertEqual(len(validate_report(base,catalog)),1)
        base['placements'][0]['needsAlpha']=True
        self.assertEqual(len(validate_report(base,catalog)),1)
        base['placements'][0]['needsAlpha']='true'
        with self.assertRaisesRegex(ValueError,'needsAlpha'):
            validate_report(base,catalog)

    def test_http_appearance_endpoint_isolated_from_atlas_actions(self):
        from api.write_world import route
        with TemporaryDirectory() as tmp:
            store=LocationAssetStore(Path(tmp))
            with store.connect() as db:
                db.execute("INSERT INTO location_assets(slug,name_en,category,revision,created_at,updated_at) VALUES('bush_01','Bush','bush',2,1,1)")
            deps=dict.fromkeys(('deco_layouts','locations','monster_spawns','npc_place_spawn',
                'npc_register_spawn','npc_spawns','options_store','request_active_studio_save',
                'run_timeline_editor_bridge','sync_monster_to_studio','timelines',
                'publication_credentials'))
            deps['location_assets']=store
            status,payload=route('/api/location-assets/bush_01/appearance',
                lambda:{'alphaEnabled':True,'expectedRevision':2},deps)
            self.assertEqual(status,200,payload)
            self.assertIs(payload['alphaEnabled'],True)
            status,err=route('/api/location-assets/bush_01/appearance',
                lambda:{'alphaEnabled':False,'expectedRevision':2},deps)
            self.assertEqual(status,400)
            self.assertIn('changed since Edit',err['error'])

    def test_shared_atlas_bindings_remain_intact(self):
        from PIL import Image
        with TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'wood_64x64_atlas.png'
            Image.new('RGBA',(64,64),(255,0,0,60)).save(source)
            store=LocationAssetStore(root)
            with store.connect() as db:
                for slug in ('bush_01','tree_01'):
                    db.execute("INSERT INTO location_assets(slug,name_en,category,revision,created_at,updated_at) VALUES(?,?,?,1,1,1)",
                        (slug,slug,'tree'))
            atlas=store.atlases.adopt_file(str(source))
            for slug in ('bush_01','tree_01'):
                store.atlases.bind('location_asset',slug,atlas['id'],allow_unpublished=True)
            before=[store.atlases.binding('location_asset',slug) for slug in ('bush_01','tree_01')]
            store.update_alpha('bush_01',{'alphaEnabled':True,'expectedRevision':1})
            after=[store.atlases.binding('location_asset',slug) for slug in ('bush_01','tree_01')]
            self.assertEqual(before,after)
            self.assertTrue(store.get('bush_01')['alphaEnabled'])
            self.assertFalse(store.get('tree_01')['alphaEnabled'])

    def test_studio_shared_policy_and_col_exclusion(self):
        appearance=(ROOT/'system/studio-plugin/modules/StudioTextureAppearance.luau').read_text()
        loader=(ROOT/'system/studio-plugin/modules/DecoAssetLoader.luau').read_text()
        scan=(ROOT/'system/studio-plugin/modules/StudioPublishedMeshHistory.luau').read_text()
        place=(ROOT/'system/studio-plugin/modules/StudioPlaceRegistrySync.luau').read_text()
        individual=(ROOT/'system/studio-plugin/modules/DecoPlacedAssetSync.luau').read_text()
        realestate=(ROOT/'system/studio-plugin/modules/StudioRealEstateModel.luau').read_text()
        for literal in ('Enum.AlphaMode.Opaque','Enum.AlphaMode.Transparency',
                        'function StudioTextureAppearance.Capture','function StudioTextureAppearance.Restore',
                        'function StudioTextureAppearance.ApplyAlpha'):
            self.assertIn(literal,appearance)
        self.assertIn('StudioTextureAppearance.ApplyLocation',loader)
        self.assertIn('if MeshPhysics.IsCollider(descendant.Name)',loader)
        self.assertIn('needsAlpha=not alphaCurrent',scan)
        self.assertIn('Texture.ApplyAlpha(change.mesh,ref.entry.alphaEnabled',place)
        self.assertIn('StudioTextureAppearance.AlphaCurrent',individual)
        self.assertIn('StudioTextureAppearance.Restore(change)',individual)
        self.assertIn('StudioTextureAppearance.Apply(',realestate)
        self.assertNotIn('ApplyLocation(',realestate)

    def test_ui_is_per_consumer_and_explicit(self):
        ui=(ROOT/'system/control-center/static/location-asset-workflow.js').read_text()
        self.assertIn('data-la-alpha',ui)
        self.assertIn("action==='apply-alpha'",ui)
        self.assertIn('/appearance',ui)
        self.assertIn('alphaEnabled:value',ui)
        self.assertIn('p.needsAlpha',ui)
        self.assertIn('alphaEnabled:Boolean(item.alphaEnabled)',ui)
        self.assertIn('scan.alphaEnabled!==Boolean(item.alphaEnabled)',ui)

if __name__=='__main__':unittest.main()
