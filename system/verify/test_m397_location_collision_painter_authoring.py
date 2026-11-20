"""M397: single authoring surface, collision publication compatibility, protected painter Sync."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
def read(name):
    return (ROOT / name).read_text(encoding='utf-8')

class M397Contract(unittest.TestCase):
    def test_identity_has_no_appearance_controls(self):
        src = read('system/control-center/static/location-asset-workflow.js')
        self.assertNotIn('data-la-appearance-mode', src)
        self.assertNotIn('data-la-visual-material', src)
        self.assertIn('data-la-model-appearance-mode', src)
        self.assertIn('data-la-model-visual-material', src)
        self.assertIn('state.modelAppearanceDraft', src)
        self.assertIn('meshOptions:state.meshOptions,', src)

    def test_retire_incompatible_collision_but_not_history(self):
        src = read('system/control-center/location_asset_store.py')
        self.assertIn("'SELECT meshes_json FROM location_asset_mesh_id_inventory '",src)
        self.assertIn("stale_collision = anchor_id not in published_ids",src)
        self.assertIn("result['collisionBlueprintNeedsCapture'] = stale_collision",src)
        self.assertIn('active_collision = None if stale_collision else collision',src)
        self.assertNotIn('DELETE FROM location_asset_collision_blueprints WHERE asset_slug=?',src[:src.index('def delete') if 'def delete' in src else 0])

    def test_painter_uses_shared_physics_and_collision(self):
        sync = read('system/studio-plugin/modules/StudioPlaceRegistrySync.luau')
        inv = read('system/studio-plugin/modules/StudioPlaceRegistryInventory.luau')
        integrity = read('system/studio-plugin/modules/StudioLocationPainterIntegrity.luau')
        self.assertIn('Physics.ApplyLocationModel(root,item.physicsNames,ref.entry.meshOptions)',sync)
        self.assertIn('Physics.RestoreLocationModel(item.physics)',sync)
        self.assertIn('if item.collision then Collision.Commit(item.collision) end',sync)
        self.assertIn('or not Collision.Current(external.model,',inv)
        self.assertIn('Collision.PrepareClear',sync)
        self.assertIn('needsPhysics=canAppearanceSync and physicsPending',inv)
        self.assertIn('LandscapeAnchorStem',integrity)
        self.assertIn('light/effect/constraint settings changed',integrity)

if __name__ == '__main__': unittest.main()

class M397CollisionPublication(unittest.TestCase):
    def test_collision_disabled_after_published_mesh_id_changes(self):
        import json, tempfile, sys
        sys.path.insert(0,str(ROOT/'system/control-center'))
        from location_asset_store import LocationAssetStore
        from test_location_collision_blueprint_m343 import sample
        with tempfile.TemporaryDirectory() as folder:
            store=LocationAssetStore(Path(folder))
            with store.connect() as db:
                db.execute('INSERT INTO location_assets(slug,name_en,category,model_asset_id,created_at,updated_at) VALUES(?,?,?,?,?,?)',
                           ('wooden_post_01','Wooden Post','decorations','100001',0.,0.))
            blueprint=sample()
            original=blueprint['anchor']['meshId']
            store.save_collision_blueprint('wooden_post_01',{'expectedRevision':0,'blueprint':blueprint})
            with store.connect() as db:
                db.execute('INSERT INTO location_asset_mesh_id_inventory(asset_slug,model_asset_id,meshes_json,observed_at) VALUES(?,?,?,?)',
                           ('wooden_post_01','100001',json.dumps([{'meshId':original,'visualNames':['wooden_post_01']}]),0.))
            self.assertEqual(store.get('wooden_post_01')['collisionBlueprintRevision'],1)
            with store.connect() as db:
                db.execute('UPDATE location_assets SET model_asset_id=? WHERE slug=?',('100002','wooden_post_01'))
                db.execute('INSERT INTO location_asset_mesh_id_inventory(asset_slug,model_asset_id,meshes_json,observed_at) VALUES(?,?,?,?)',
                           ('wooden_post_01','100002',json.dumps([{'meshId':'99999999','visualNames':['wooden_post_01']}]),0.))
            current=store.get('wooden_post_01')
            self.assertEqual(current['collisionBlueprintRevision'],0)
            self.assertTrue(current['collisionBlueprintNeedsCapture'])
            self.assertEqual(current['collisionBlueprintRetainedRevision'],1)
            self.assertEqual(store.collision_blueprint('wooden_post_01')['revision'],1)
