"""MNPC runtime projection and actual controller Lua doubles (not native Roblox)."""
from pathlib import Path
import sys
import subprocess
import shutil
import unittest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services.mnpc_lod_runtime import asset, projection, export, affects_runtime
from services.mnpc_lod_alignment import identity
import test_m633_mnpc_lod_authoring as fixture_module


class RuntimeProjection(unittest.TestCase):
    def test_missing_stale_unverified_and_verified(self):
        p = {'enabled': True, 'full': 100, 'hide': 200, 'hysteresis': 10}
        row = dict(kind='monster',slug='same',profile=p,revision=1,fullFingerprint='a',sourceSha256='b',
                   modelAssetId='900',imageAssetId='901',fullModelId='101',status='PUBLISHED',alignmentStatus='GEOMETRY_VERIFIED')
        row['alignment'] = dict(identity=identity(row),meshId='123',size=[1,2,3],rootCFrame=[0,0,0,1,0,0,0,1,0,0,0,1])
        self.assertEqual(asset(row)['meshId'],'123')
        self.assertNotEqual(asset(row)['meshId'],row['modelAssetId'])
        missing={**row,'kind':'npc','status':'NOT_REGISTERED','alignment':None}
        overview={'settings':{'defaults':p},'items':[row,missing]}
        result=projection(overview)
        self.assertEqual(result['actors']['npc:same'],{'profile':p})
        self.assertEqual(result['actors']['monster:same']['asset']['imageId'],'901')
        self.assertIsNone(asset({**row,'revision':2}))
        self.assertIsNone(asset({**row,'status':'FULL_CHANGED'}))
        self.assertIsNone(asset({**row,'alignmentStatus':'NOT_VERIFIED'}))
        self.assertIsNone(asset({**row,'alignment':{**row['alignment'],'rootCFrame':[0,0,0,-1,0,0,0,1,0,0,0,1]}}))
        self.assertIsNone(asset({**row,'alignment':{**row['alignment'],'size':[1,float('nan'),3]}}))

    def test_generated_registry_with_no_lods(self):
        fixture=fixture_module.MnpcAuthoring('test_catalog_kind_identity_and_additive_backup')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        path=export(fixture.owner)
        data=path.read_text()
        self.assertIn('monster:same',data)
        self.assertIn('npc:same',data)
        self.assertIn('enabled"] = true',data)
        self.assertNotIn('meshId',data)
        old=path.stat().st_mtime_ns
        self.assertEqual(export(fixture.owner),path)
        self.assertEqual(path.stat().st_mtime_ns,old)
        for path in ['/api/npcs/same/publish','/api/npc-equipment/sync','/api/monster-animations/assign','/api/texture-atlases/publish-reviewed','/api/lod-manager/mnpc/settings']:
            self.assertTrue(affects_runtime(path))
        self.assertFalse(affects_runtime('/api/studio-bridge/heartbeat'))

    def test_controller_oracle(self):
        lua=shutil.which('texlua') or shutil.which('lua')
        if not lua: self.skipTest('Standalone Lua unavailable')
        subprocess.run([lua,str(ROOT/'system/verify/mnpc_lod_m638.lua'),str(ROOT)],check=True,timeout=15)

    def test_common_scheduler_and_existing_combat(self):
        source=(ROOT/'src/client/world/LocationWorldStreamer.luau').read_text()
        controller=(ROOT/'src/client/actor/MnpcLodController.luau').read_text()
        self.assertIn('pcall(mnpc.Step, mnpc, dt)',source)
        self.assertNotIn('Heartbeat:Connect',controller)
        self.assertNotIn('RemoteEvent',controller)
        self.assertIn('TRANSITIONS = 4',controller)
        self.assertIn('MNPC_LOD1_RED_DUMMY',controller)
        self.assertIn('part.CanQuery = false',controller)
        for path in ('src/client/actor/NpcAttackLocomotionController.luau','src/client/monster/MonsterAttackLocomotionController.luau'):
            text=(ROOT/path).read_text()
            self.assertIn('RigObserver.Watch',text)
            self.assertIn('LocalVisibility.Full',text)
        self.assertIn('GameOptions.MnpcDemandEnabled()', (ROOT/'src/server/actor/MnpcDemandLifecycle.luau').read_text())

if __name__=='__main__': unittest.main()
