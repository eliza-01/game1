from pathlib import Path
import json
import shutil
import sys
import tempfile
import unittest
from threading import RLock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'system/control-center'))
from services import hitbox_asset_authoring as authoring
from services import hitbox_asset_registry as registry
from api import write_world


class Catalog:
    def __init__(self):
        self._lock = RLock()
        self.row = {'fullFingerprint': 'current', 'fullStatus': 'PUBLISHED',
                    'fullIdentity': {'modelId': '123', 'equipment': {}}}

    def describe(self, kind, slug):
        return self.row


def capture_payload(slug='gremlin'):
    return {'schemaVersion': 2, 'entries': [{
        'key': '1:body:rbxassetid://456:1.000000,1.000000,1.000000|identity:'+slug+'|head:head|parent:neck',
        'signature': json.dumps([[[['body'], 'rbxassetid://456', [0]*12, [0]*12, []]],
                                 [], ['body','head'], ['body','neck'], [], [[0]*12,[0]*12]]),
        'definition': {'broadRadius': 4, 'sourceVertexCount': 50,
                       'bodyBoxes': [{'kind':'mesh','recordIndex':1,'center':[0,0,0],'size':[1,2,3]}],
                       'headBox': {'kind':'head','boneName':'head','center':[0,0,0],'size':[1,1,1]}}}]}


class HitboxAssetAuthoring(unittest.TestCase):
    def test_revision_pinned_capture_and_compilation(self):
        catalog=Catalog()
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'registry.luau'
            target.write_text(registry.render({'schemaVersion': 2, 'entries': []}), encoding='utf-8')
            def bridge(command):
                self.assertEqual(command, {'kind':'monster','slug':'gremlin','modelId':'123','fullFingerprint':'current','equipment':{}})
                return capture_payload()
            for _ in range(2):
                result=authoring.capture(catalog,'monster','gremlin',{'fullFingerprint':'current'},bridge=bridge,destination=target)
                self.assertEqual(result['entries'],1)
                self.assertEqual(result['nativeCoverage'],'NOT_RUN')
            self.assertEqual(registry.read_registry(target),registry.normalize(capture_payload()))
            before=target.read_bytes()
            def stale(command):
                catalog.row['fullFingerprint']='new'
                return capture_payload()
            with self.assertRaisesRegex(ValueError,'changed during capture'):
                authoring.capture(catalog,'monster','gremlin',{'fullFingerprint':'current'},bridge=stale,destination=target)
            self.assertEqual(before,target.read_bytes())
            with self.assertRaisesRegex(ValueError,'FULL changed'):
                authoring.capture(catalog,'monster','gremlin',{'fullFingerprint':'current'},bridge=bridge,destination=target)
            self.assertEqual(before,target.read_bytes())

    def test_invalid_actor_fallback_and_transport_failures_do_not_write(self):
        catalog=Catalog()
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'registry.luau'; target.write_text(registry.render({'schemaVersion': 2, 'entries': []}), encoding='utf-8')
            before=target.read_bytes()
            fallback=capture_payload(); fallback['entries'][0]['definition']['bodyBoxes'][0]['kind']='root'
            for data in [capture_payload('other'),fallback,{'schemaVersion':2,'entries':[]}]:
                with self.assertRaises(ValueError):
                    authoring.capture(catalog,'monster','gremlin',{'fullFingerprint':'current'},bridge=lambda _:data,destination=target)
                self.assertEqual(before,target.read_bytes())
            def failed(_): raise RuntimeError('Studio not connected')
            with self.assertRaisesRegex(RuntimeError,'Studio not connected'):
                authoring.capture(catalog,'monster','gremlin',{'fullFingerprint':'current'},bridge=failed,destination=target)
            self.assertEqual(before,target.read_bytes())

    def test_bridge_route_and_ui(self):
        from unittest.mock import patch
        with patch.object(authoring,'capture',return_value={'status':'CAPTURED'}) as capture:
            owner=Catalog(); owner._actor=lambda *_:None
            self.assertEqual(write_world.route('/api/lod-manager/mnpc/npc/guard/hitboxes',lambda:{'fullFingerprint':'current'},{'mnpc_lod':owner}),(200,{'status':'CAPTURED'}))
            capture.assert_called_once_with(owner,'npc','guard',{'fullFingerprint':'current'})
        plugin=ROOT/'system/studio-plugin'
        manifest=json.loads((plugin/'plugin.project.json').read_text('utf-8'))
        for name in ('StudioHitboxAssetCapture','StudioHitboxAssetCommand'):
            self.assertTrue((plugin/manifest['tree']['modules'][name]['$path']).is_file())
        self.assertIn('handleHitboxCapture(data)',(plugin/'Game1Bridge.server.luau').read_text('utf-8'))
        ui=(ROOT/'system/control-center/static/mnpc-lod-manager.js').read_text('utf-8')
        self.assertIn('/hitboxes',ui)
        self.assertIn('mnpc-hitboxes-all',ui)
        self.assertIn('mnpc-hitboxes-all',(ROOT/'system/control-center/static/index.html').read_text('utf-8'))

    def test_same_oracle_detached_no_combat_registration(self):
        combat=(ROOT/'src/server/combat/EntityHitboxService.luau').read_text('utf-8')
        capture=combat.split('function EntityHitboxService.CaptureAsset',1)[1].split('function EntityHitboxService.QueryDamageablesInBox',1)[0]
        self.assertIn('entity.Parent == nil',capture)
        self.assertIn('resolveGeometry(binding, true)',capture)
        self.assertIn('HitboxDefinitionBuilder.BuildUncached(binding)',combat)
        self.assertNotIn('index:Register',capture)
        self.assertIn('error("mesh unavailable:',combat)
        self.assertIn('HitboxAssetDefinitions.AuthoringRow',capture)
        plugin=(ROOT/'system/studio-plugin/modules/StudioHitboxAssetCapture.luau').read_text('utf-8')
        for call in ('lifecycle.Create(', 'lifecycle.PrepareShell(', 'lifecycle.AttachRig(', 'equipment.Equip(', '.EnsureRuntimeAnimationRoot(', '.Align(', 'hitboxes.CaptureAsset(', 'entity:Destroy()'):
            self.assertIn(call,plugin)
        self.assertNotIn('lifecycle.Publish',plugin)
