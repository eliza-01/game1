"""M221 contract tests: no displaced Model replacement, real guarded mesh sync.

These tests exercise the HTTP bridge/audit in Python and statically pin the
Luau safety contract. They do NOT substitute for Roblox Studio Edit-mode smoke.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest import mock
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services.location_asset_sync_history import LocationAssetSyncHistory
from services import studio_deco_bridge


class MemoryAudit:
    def __init__(self):
        self.rows = []
    def ensure_schema(self):
        return None
    def append(self, event):
        if not any(row['operationId'] == event['operationId'] for row in self.rows):
            self.rows.append(dict(event))
    def page(self, slug, *, limit, before=None):
        return {'events': [x for x in self.rows if x['slug'] == slug][:limit],
                'nextCursor': None}


class M221InPlaceGeometry(TestCase):
    def source(self, path):
        return (ROOT / path).read_text(encoding='utf-8')

    def test_one_shared_replacement_module_used_by_estate_and_location(self):
        deco = self.source('system/studio-plugin/modules/DecoPlacedAssetSync.luau')
        house = self.source('system/studio-plugin/modules/StudioRealEstatePlacedVisualSync.luau')
        helper = self.source('system/studio-plugin/modules/StudioManagedRigSwap.luau')
        project = self.source('system/studio-plugin/plugin.project.json')
        self.assertIn('StudioManagedRigSwap', project)
        self.assertNotIn('StudioMeshInPlaceSync', project)
        for source in (deco, house):
            self.assertIn('RigSwap.Prepare(', source)
            self.assertIn('RigSwap.Commit(', source)
            self.assertIn('RigSwap.Rollback(', source)
            self.assertIn('RigSwap.Finalize(', source)
        self.assertIn('function RigSwap.AlignToAnchor(', helper)
        self.assertIn('function RigSwap.Rollback(', helper)
        self.assertIn('function RigSwap.Finalize(', helper)
        self.assertNotIn('ApplyMesh(', deco + house + helper)
        self.assertNotIn('model:Destroy()', deco)
        self.assertIn('descendant:GetAttribute(SLUG) == slug', deco)
        self.assertIn('descendant:GetAttribute(INSTANCE)', deco)

    def test_skinned_source_is_copied_without_meshpart_applymesh(self):
        deco = self.source('system/studio-plugin/modules/DecoPlacedAssetSync.luau')
        helper = self.source('system/studio-plugin/modules/StudioManagedRigSwap.luau')
        self.assertIn('stage = (published :: Model):Clone()', deco)
        self.assertIn('stage:ScaleTo(model:GetScale())', deco)
        self.assertIn('History.Provenance(model,previousPublished)', deco)
        self.assertIn('rigChildren(stage)', deco)
        self.assertIn('for _, child in ipairs(plan.incoming) do child.Parent = plan.root end', helper)
        self.assertNotIn('WrapLayer', helper)
        self.assertNotIn('WrapTarget', helper)
        self.assertNotIn('Bone', helper)

    def test_preflight_before_mutation_and_audit_after_commit(self):
        deco = self.source('system/studio-plugin/modules/DecoPlacedAssetSync.luau')
        prep = deco.index('RigSwap.Prepare(model, previousChildren, nextChildren,')
        commit = deco.index('RigSwap.Commit(item.swap)')
        stamp = deco.index('model:SetAttribute("Game1DecoPublishedModelSha256", publishedSha)', commit)
        self.assertLess(prep, commit)
        self.assertLess(commit, stamp)
        self.assertIn('if not prepared then', deco)
        self.assertIn('RigSwap.Rollback(item.swap)', deco)
        self.assertIn('Game1DecoSyncHistory', deco)

    def test_old_studio_plugin_cannot_acknew_schema(self):
        cmd = self.source('system/studio-plugin/modules/StudioDecoSyncCommands.luau')
        bridge = self.source('system/control-center/services/studio_deco_bridge.py')
        self.assertIn('schemaVersion~=9', cmd)
        self.assertIn('schemaVersion=9', cmd)
        self.assertIn("'schemaVersion': 9", bridge)
        self.assertIn('"geometryUpdated"', cmd)
        self.assertIn('"meshPartsUpdated"', cmd)
        self.assertIn("'geometryUpdated', 'meshPartsUpdated'", bridge)
        with self.assertRaises(ValueError):
            studio_deco_bridge.run_deco_refresh_bridge(slug='',binding_revision=1,
                model_asset_id='123',atlas_asset_id='456')

    def test_history_accepts_actual_model_replacement_and_legacy_events(self):
        with TemporaryDirectory() as directory:
            store = LocationAssetSyncHistory(Path(directory), database=MemoryAudit())
            current = {
                'operationId':'1'*32, 'models':2, 'parts':0,
                'matchedModels':2, 'pendingGeometry':0,
                'geometryUpdated':2, 'meshPartsUpdated':4,
                'changes':[{'kind':'model','oldId':'300','newId':'500','count':2}],
                'instances':[
                    {'instanceId':str(i), 'studioPath':f'Workspace.Location.{i}',
                     'changes':[{'kind':'model','oldId':'300','newId':'500','count':1}]}
                    for i in range(2)],
            }
            store.append(slug='campfire_01', binding_revision=2, studio=current)
            legacy = dict(current,operationId='2'*32, models=1,
                changes=[{'kind':'model_reference','oldId':'1','newId':'2','count':1}],
                instances=[{'instanceId':'old','studioPath':'Workspace.Old',
                            'changes':[{'kind':'atlas','oldId':'7','newId':'9','count':1}]}])
            store.append(slug='campfire_01', binding_revision=3, studio=legacy)
            self.assertEqual(len(store.list('campfire_01')),2)
            self.assertEqual(store.list('campfire_01')[0]['changes'][0]['kind'],'model')

    def test_ui_reports_geometry_and_requires_explicit_confirmation(self):
        ui = self.source('system/control-center/static/studio-sync.js')
        row = self.source('system/control-center/static/deco-assets.js')
        self.assertIn('geometry updated ${Number(studio?.geometryUpdated', ui)
        self.assertIn('meshPartsUpdated', ui)
        self.assertIn('window.confirm', self.source('system/control-center/static/location-asset-workflow.js'))
        self.assertIn('window.game1LocationAssetWorkflow.startScan(slug)', row)
        self.assertIn('Model geometry', row)

    def test_m215_rebuild_cannot_be_reintroduced(self):
        manager = self.source('system/studio-plugin/modules/DecoManager.luau')
        self.assertNotIn('RefreshModels', manager)
        self.assertIn('DecoPlacedAssetSync.RefreshIds(', manager)
        self.assertIn('expectedAtlasId, self.loader, scanned, selected)', manager)
        self.assertNotIn('currentRow:Destroy()', manager)
        self.assertIn('replacedModels = 0', manager)
