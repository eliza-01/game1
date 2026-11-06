"""M248: current published Mesh IDs remain discoverable after Identity rename.

Studio-specific object behavior requires a real Edit-mode test; these guards
verify the scan/selection contract and prove that the renamed SQLite inventory
still contains the published identities used by the scanner.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from location_asset_store import LocationAssetStore


class ScopedCurrentMeshM248(unittest.TestCase):
    def source(self, path: str) -> str:
        return (ROOT / path).read_text(encoding='utf-8')

    def test_scan_does_not_require_legacy_or_owner_for_current_visual_id(self):
        code = self.source('system/studio-plugin/modules/StudioPublishedMeshHistory.luau')
        scan = code.split('function Inventory.Scan(', 1)[1]
        self.assertIn('currentVisualIds[entry.meshId]=true', scan)
        self.assertIn('owner==nil and currentVisualIds[meshId]==true', scan)
        self.assertIn('if old or owner or currentUnlinked then', scan)
        self.assertIn('not MeshPhysics.IsCollider(part.Name)', scan)
        self.assertIn('part:GetAttribute("Game1DecoPhysicsOnly") ~= true', scan)
        self.assertIn('managed=owner~=nil', scan)  # read-only until explicit repair/link
        self.assertIn('if entry.managed then', scan)  # pending Sync only for owned roots

    def test_unlinked_part_does_not_claim_handmade_parent_model(self):
        code = self.source('system/studio-plugin/modules/StudioPublishedMeshHistory.luau')
        manager = self.source('system/studio-plugin/modules/DecoManager.luau')
        self.assertIn('local container=owner or legacyRoot or part', code)
        self.assertIn('selectTarget=container', code)
        self.assertIn('local chosen = match.selectTarget or match.root or part', manager)
        self.assertIn('string.sub(chosen:GetFullName(),1,240) ~= match.row.modelPath', manager)
        self.assertIn('self.Selection:Set(selected)', manager)
        self.assertIn('Для исправления идентификаторов используйте Repair в Place Registry',
                      self.source('system/control-center/static/location-asset-workflow.js'))

    def test_renamed_asset_preserves_current_visual_mesh_inventory(self):
        with TemporaryDirectory() as tmp:
            store = LocationAssetStore(Path(tmp))
            with store.connect() as db:
                db.execute("""INSERT INTO location_assets(slug,name_en,category,model_path,
                    model_sha256,model_asset_id,model_published_sha256,revision,created_at,updated_at)
                    VALUES('stone_fence_pillar_01','Old','fence','a.fbx','hash','119135753549307',
                    'hash',1,1,1)""")
                db.execute("""INSERT INTO location_asset_publications
                    (asset_slug,kind,revision,asset_id,operation_path,sha256,published_at)
                    VALUES('stone_fence_pillar_01','model',1,'119135753549307','ops/one','hash',1)""")
            meshes = [{'meshId':'112049281261824','count':1,
                       'visualNames':['stone_fence_pillar_01']}]
            store.record_mesh_id_inventory('stone_fence_pillar_01', [
                {'modelAssetId':'119135753549307','meshes':meshes}])
            result = store.rename_identity('stone_fence_pillar_01', {
                'slug':'stone_pillar_01','nameEn':'Stone Pillar 01',
                'category':'fence','destructible':False,'expectedRevision':1})
            self.assertEqual(result['slug'], 'stone_pillar_01')
            self.assertEqual(store.aliases_for('stone_pillar_01'), ['stone_fence_pillar_01'])
            self.assertEqual(store.model_publication_ids('stone_pillar_01'), ['119135753549307'])
            self.assertEqual(store.mesh_id_inventory('stone_pillar_01')[0]['meshes'], meshes)

if __name__ == '__main__':
    unittest.main()
