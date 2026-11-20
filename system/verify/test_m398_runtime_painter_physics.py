"""M398: Painter visual streaming must be opt-in by verified Scan evidence.

Every Fire/Light/Bone/Weld and the LandscapePainter-owned root survives the
XML compilation. Invalid physical policy or unverified owner fails closed.
"""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system' / 'control-center'))
sys.path.insert(0, str(ROOT / 'system' / 'verify'))
from services.location_runtime_build import RuntimePlaceBuilder, build_rows
from services.location_streaming_config import DEFAULT_SETTINGS
from test_m390_location_composite_runtime import item, mesh, snapshot


class FakeRevisions:
    def __init__(self, report): self.report=report
    def get(self, _revision): return self.report


class FakeRegistry:
    def __init__(self, report): self.revisions=FakeRevisions(report)


class PainterRuntime(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        (self.root/'place').mkdir()
        scene=ET.Element('roblox',version='4')
        workspace=item(scene,'Workspace','Workspace','WS')
        item(scene,'ReplicatedStorage','ReplicatedStorage','RS')
        painter=item(workspace,'Model','Game1LandscapeDecor','PAINTER')
        assets=item(painter,'Folder','Assets','ASSETS')
        lamp=item(assets,'Model','lantern_02__12345678','LAMP')
        carrier=mesh(lamp,'rig_carrier','CARRIER','98000')
        bone=item(carrier,'Bone','root','BONE')
        attachment=item(bone,'Attachment','fx','ATTACH')
        item(attachment,'PointLight','PointLight','LIGHT')
        item(attachment,'Fire','Fire','FIRE')
        item(attachment,'ParticleEmitter','sparks','SPARKS')
        visual=mesh(lamp,'lantern_02','VISUAL','99000')
        item(visual,'Weld','Weld','JOINT')
        self.path='Workspace.Game1LandscapeDecor.Assets.lantern_02__12345678'
        self.external={
            'kind':'landscape_attachment','slug':'lantern_02','authorSlug':'lantern_02',
            'path':self.path,'ownerPath':self.path,'name':'lantern_02__12345678',
            'branchStrokeId':'','anchorKind':'surface','reason':'LandscapePainter authored attachment',
            'key':'x1','review':False,'protectedFromRuntime':True,
            'runtimeCandidate':True,'hierarchy':snapshot(lamp),
            'pivotEvidence':{'modelPivot':[0,3,4,1,0,0,0,1,0,0,0,1]},
            'canSync':False,'needsTexture':False,'needsCollision':False,
            'needsPhysics':False,'needsOwnerCleanup':False,
        }
        self.report={'placements':[],'protected':[self.external]}
        self.overview={'snapshot':{'freshness':'SCANNED_THIS_SESSION','catalogMatches':True,
                                   'revisionId':189},'items':[{
            'slug':'lantern_02','count':0,'protectedCount':1,
            'fullStatus':'PUBLISHED','fullModelId':'12345',
            'lod1Status':'NOT_REGISTERED','lod1ModelId':'',
        }]}
        self.settings=copy.deepcopy(DEFAULT_SETTINGS)
        self.settings['modes']={'lantern_02':'full'}
        self.source=self.root/'place'/'game1_runtime_source.rbxlx'
        ET.ElementTree(scene).write(self.source,encoding='utf-8',xml_declaration=True)

    def rows(self):
        return build_rows(self.overview, FakeRegistry(self.report), self.settings)

    def test_compiles_painter_without_losing_effects_or_changing_authoring(self):
        selected=self.rows()
        self.assertEqual(len(selected),1)
        self.assertTrue(selected[0]['placementId'].startswith('painter_'))
        builder=RuntimePlaceBuilder(self.root)
        preflight=builder.inspect(selected,self.settings)
        result=builder.prepare(selected,expected_sha=preflight['sourceSha256'],
            snapshot_id=189,catalog_digest='unit',settings=self.settings)
        runtime=ET.parse(result['runtimePath'])
        models=[node for node in runtime.iter('Item') if node.get('referent')=='LAMP']
        self.assertEqual(len(models),1)
        children=[node.get('class') for node in models[0].iter('Item')]
        self.assertEqual(children.count('MeshPart'),1) # carrier
        self.assertEqual(children.count('Part'),1) # visual proxy
        for preserved in ('Bone','Attachment','PointLight','Fire','ParticleEmitter','Weld'):
            self.assertIn(preserved,children)
        self.assertFalse(result['publishAllowed'])
        self.assertEqual(self.source.read_bytes(),Path(result['backupPath']).read_bytes())
        self.assertEqual(result['removedVisualMeshParts'],1)

    def test_unscanned_painter_sibling_stops_preflight(self):
        selected=self.rows()
        scene=ET.parse(self.source)
        assets=next(n for n in scene.iter('Item') if n.get('referent')=='ASSETS')
        item(assets,'Model','lantern_02__87654321','UNSCANNED')
        scene.write(self.source,encoding='utf-8',xml_declaration=True)
        with self.assertRaisesRegex(ValueError,'Uninventoried target Location Model'):
            RuntimePlaceBuilder(self.root).inspect(selected,self.settings)

    def test_current_tree_is_not_accepted_via_retired_skinned_exception(self):
        inventory=(ROOT/'system/studio-plugin/modules/StudioPlaceRegistryInventory.luau').read_text()
        history=(ROOT/'system/studio-plugin/modules/StudioPublishedMeshHistory.luau').read_text()
        self.assertNotIn('MatchesRetiredSkinnedPhysics', inventory+history)

    def test_physics_validator_and_sync_share_writer(self):
        core=(ROOT/'src/shared/world/MeshPhysicsCore.luau').read_text()
        inventory=(ROOT/'system/studio-plugin/modules/StudioPlaceRegistryInventory.luau').read_text()
        sync=(ROOT/'system/studio-plugin/modules/StudioPlaceRegistrySync.luau').read_text()
        self.assertIn('function Core.LocationNeedsPhysics',core)
        self.assertIn('Physics.LocationNeedsPhysics(candidatePart,entry.meshOptions)',inventory)
        self.assertIn('Physics.ApplyLocationModel(root,namedVisuals(ref),ref.entry.meshOptions)',sync)
        self.assertIn('Physics.RestoreLocationModel(item.priorPhysics)',sync)

    def test_single_distance_owner_controls_client_effects(self):
        client=(ROOT/'src/client/world/LocationWorldStreamer.luau').read_text()
        adapter=(ROOT/'src/client/world/LocationCompositeVisual.luau').read_text()
        self.assertIn('LocationCompositeVisual.SetEffects(record, record.actual ~= "UNLOADED")',client)
        self.assertIn('function Adapter.SetEffects(record: any, active: boolean)',adapter)
        self.assertNotIn('RunService.Heartbeat',adapter)
        for effect in ('Light','Fire','Smoke','Sparkles','ParticleEmitter','Beam','Trail'):
            self.assertIn(f'IsA("{effect}")',adapter)

    def test_external_review_stops_preflight(self):
        self.external['runtimeCandidate']=False
        with self.assertRaisesRegex(ValueError,'not Runtime-verified'):
            self.rows()

    def test_protected_collision_cannot_be_boxified(self):
        visual=next(n for n in self.external['hierarchy'] if n['name']=='lantern_02')
        visual['canCollide']=True
        visual['collisionFidelity']='Enum.CollisionFidelity.PreciseConvexDecomposition'
        with self.assertRaisesRegex(ValueError,'Box fidelity'):
            self.rows()

    def test_no_stale_nested_effect_structure_is_accepted(self):
        selected=self.rows()
        scene=ET.parse(self.source)
        fire=next(n for n in scene.iter('Item') if n.get('referent')=='FIRE')
        parent=next(n for n in scene.iter('Item') if n.get('referent')=='ATTACH')
        parent.remove(fire)
        scene.write(self.source,encoding='utf-8',xml_declaration=True)
        with self.assertRaisesRegex(ValueError,'hierarchy differs from Scan'):
            RuntimePlaceBuilder(self.root).inspect(selected,self.settings)


if __name__=='__main__': unittest.main()
