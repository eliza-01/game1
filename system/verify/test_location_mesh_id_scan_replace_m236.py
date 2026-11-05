"""M236: read-only ID scan, scoped replacement, historical inventory and safety gates.

Source assertions do not substitute for real Roblox Studio Edit-mode smoke tests.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'system/control-center'))
from location_asset_store import LocationAssetStore
from services.location_asset_sync_history import LocationAssetSyncHistory
from services import studio_deco_bridge as bridge


class MemoryAudit:
    def __init__(self): self.events=[]
    def ensure_schema(self): pass
    def append(self,event): self.events.append(event)
    def page(self,slug,*,limit,before=None):
        return {'events':self.events[:limit], 'nextCursor':None}


class MeshHistoryM236(unittest.TestCase):
    @staticmethod
    def source(path):return (ROOT/path).read_text('utf-8')

    def test_database_stores_each_published_model_mesh_id_independently(self):
        with TemporaryDirectory() as directory:
            store=LocationAssetStore(Path(directory))
            with store.connect() as db:
                db.execute('''INSERT INTO location_asset_publications
                    (asset_slug,kind,revision,asset_id,operation_path,sha256,published_at)
                    VALUES(?,?,?,?,?,?,?)''',('tree_01','model',1,'123456','op1','a'*64,1.0))
            self.assertIn('123456',store.model_publication_ids('tree_01'))
            record={'modelAssetId':'123456','meshes':[{'meshId':'33333','count':2},
                        {'meshId':'44444','count':1}]}
            store.record_mesh_id_inventory('tree_01',[record])
            self.assertEqual(store.mesh_id_inventory('tree_01'),[record])
            with self.assertRaises(ValueError):
                store.record_mesh_id_inventory('tree_01',[dict(record,meshes=[{'meshId':'3','count':0}])])

    def test_only_replacement_marks_atlas_synced(self):
        api=self.source('system/control-center/api/write_world.py')
        action=api.split('if path == "/api/location-assets/studio-sync":',1)[1].split("if path.startswith('/api/texture-atlases/variants/')",1)[0]
        self.assertIn("phase = str(payload.get('phase') or 'scan')",action)
        self.assertIn("if phase == 'scan'",action)
        self.assertLess(action.index("if phase == 'scan':\n                if"),action.index("deps['location_asset_sync_history'].append("))
        self.assertIn("location_assets.record_mesh_id_inventory",action)
        self.assertIn("location_assets.atlases.mark_synced",action)

    def test_plugin_scans_readonly_and_replaces_only_with_token(self):
        manager=self.source('system/studio-plugin/modules/DecoManager.luau')
        history=self.source('system/studio-plugin/modules/StudioPublishedMeshHistory.luau')
        placed=self.source('system/studio-plugin/modules/DecoPlacedAssetSync.luau')
        cmds=self.source('system/studio-plugin/modules/StudioDecoSyncCommands.luau')
        self.assertNotIn('selection:Set(selected)',history)
        scan=manager.split('function DecoManager:previewMeshSync(',1)[1].split('function DecoManager:refreshRegistry(',1)[0]
        self.assertNotIn('DecoPlacedAssetSync.RefreshIds',scan)
        self.assertIn('self.meshSyncPreview=nil',scan)
        self.assertIn('preview.token~=scanToken',manager)
        self.assertIn('root:GetPivot()~=snap.pivot',manager)
        self.assertIn('parent=part.Parent,frame=part:GetPivot(),size=part.Size',manager)
        self.assertIn('part:GetPivot()~=snap.frame or part.Size~=snap.size',placed)
        self.assertIn('History.Provenance(model,previousPublished)',placed)
        self.assertIn('History.MatchesInventory(model,entry)',placed)
        self.assertIn('if #actual ~= #inventory.meshes then return false end',history)
        self.assertNotIn('MeshAnchor.Match(',placed)
        self.assertNotIn('ApplyMesh(',placed)
        self.assertNotIn('model:Destroy()',placed)
        self.assertIn('RigSwap.Prepare(',placed)
        self.assertIn('preferredPrimary=stage.PrimaryPart',placed)
        self.assertIn('RigSwap.Rollback(',placed)
        self.assertIn('schemaVersion~=9',cmds)
        self.assertIn('command.phase=="scan"',cmds)

    def test_manually_added_physical_parts_are_never_silently_deleted(self):
        source=self.source('system/studio-plugin/modules/StudioPublishedMeshHistory.luau')
        check=source.split('function Inventory.VerifyChildren(',1)[1].split('function Inventory.Scan(',1)[0]
        self.assertIn('expectedMeshes[mid]',check)
        self.assertIn('actualMeshes[mid] ~= count',check)
        self.assertIn('expectedOtherParts[part.ClassName]',check)
        self.assertIn('actualOtherParts[className] ~= count',check)
        self.assertIn('no Place geometry modified',check)
        self.assertIn('local expectedTree = signatures(oldChildren)', check)
        self.assertIn('local actualTree = signatures(children)', check)
        self.assertIn('unverified placed rig descendant', check)
        self.assertIn('item:IsA("SurfaceAppearance")', check)

    def test_ui_automatic_button_based_on_real_differences(self):
        ui=self.source('system/control-center/static/location-asset-workflow.js')
        client=self.source('system/control-center/static/studio-sync.js')
        self.assertIn("mesh&&texture?'Replace Texture + Mesh'",ui)
        self.assertIn(":'Replace Texture'",ui)
        self.assertIn("mesh?'Replace Mesh'",ui)
        self.assertIn('Найдено ${Number(selected.foundMeshParts||0)} MeshPart',ui)
        self.assertIn('scanLocation(state.slug)',ui)
        self.assertIn('replaceLocation(state.slug,token,keys)',ui)
        self.assertIn('window.confirm',ui)
        self.assertIn("phase:'scan'",client)
        self.assertIn("phase:'replace'",client)
        self.assertIn("return scanLocation(slug); // Old callers are never destructive.",client)

    def test_audit_has_model_and_mesh_id_sets(self):
        with TemporaryDirectory() as directory:
            log=LocationAssetSyncHistory(Path(directory),database=MemoryAudit())
            row={'operationId':'f'*32,'models':1,'parts':0,'matchedModels':1,
                 'pendingGeometry':0,'changes':[{'kind':'model','oldId':'12345','newId':'67890','count':1}],
                 'instances':[{'instanceId':'a','studioPath':'Workspace.a',
                    'changes':[{'kind':'model','oldId':'12345','newId':'67890','count':1}],
                    'meshIdsBefore':[{'meshId':'33333','count':1}],
                    'meshIdsAfter':[{'meshId':'44444','count':2}]}]}
            event=log.append(slug='tree_01',binding_revision=3,studio=row)
            self.assertEqual(event['instances'][0]['meshIdsAfter'][0]['meshId'],'44444')
            self.assertIn('meshIdRevisions',self.source('system/control-center/services/mysql_asset_replacement_audit.py'))

    def test_transport_schema_rejects_missing_selection_or_unscoped_slug(self):
        with self.assertRaises(ValueError):
            bridge.run_deco_refresh_bridge(slug='',binding_revision=1,
                model_asset_id='123',atlas_asset_id='456',phase='scan',model_history=['123'])
        with self.assertRaises(ValueError):
            bridge.run_deco_refresh_bridge(slug='tree_01',binding_revision=1,
                model_asset_id='123',atlas_asset_id='456',phase='replace',scan_token='')

if __name__=='__main__':unittest.main()
