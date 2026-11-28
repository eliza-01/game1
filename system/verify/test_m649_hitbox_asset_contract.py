from pathlib import Path
import importlib.util
import json
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / 'system/control-center/services/hitbox_asset_registry.py'
spec = importlib.util.spec_from_file_location('hitbox_asset_registry', SERVICE)
registry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(registry)
COMBAT = ROOT / 'src/server/combat'


def payload():
    part = [['mesh'], 'rbxassetid://123', [0]*12, [0]*12, []]
    return {'schemaVersion': 2, 'entries': [{'key':'key','signature':json.dumps([[part],[],[],[],[],[[0]*12,[0]*12]]),'definition':{
        'broadRadius':4,'sourceVertexCount':2,'bodyBoxes':[{'kind':'mesh','recordIndex':1,'center':[0,0,0],'size':[1,2,3]}]}}]}


class HitboxAssetContract(unittest.TestCase):
    def test_generator_roundtrip_and_atomic_conflict(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)/'registry.luau'
            src = Path(td)/'capture.json'
            path.write_text(registry.render({'schemaVersion': 2, 'entries': []}), encoding='utf-8')
            data = payload(); src.write_text(json.dumps(data), encoding='utf-8')
            self.assertEqual(registry.import_capture(src,path),1)
            self.assertEqual(registry.read_registry(path),registry.normalize(data))
            self.assertEqual(registry.import_capture(src,path),1)
            before=path.read_bytes()
            data['entries'][0]['definition']['broadRadius']=5
            src.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'conflicting'): registry.import_capture(src,path)
            self.assertEqual(before,path.read_bytes())

    def test_rejects_bad_schema_geometry_and_duplicate(self):
        for field,value in [('size',[0,2,3]),('size',[1,float('nan'),3]),('recordIndex',2),('kind','root')]:
            data=payload(); data['entries'][0]['definition']['bodyBoxes'][0][field]=value
            with self.assertRaises(ValueError): registry.normalize(data)
        data=payload(); data['schemaVersion']=1
        with self.assertRaises(ValueError): registry.normalize(data)
        data=payload(); data['entries']*=2
        with self.assertRaises(ValueError): registry.normalize(data)

    def test_real_module_leases_and_asset_capture(self):
        lua=shutil.which('texlua') or shutil.which('lua')
        if not lua: self.skipTest('Standalone Lua unavailable')
        with tempfile.TemporaryDirectory() as td:
            geom=(COMBAT/'HitboxMeshGeometryCache.luau').read_text(encoding='utf-8')
            geom=geom.replace('local geometryCache: { [string]: any }','local geometryCache').replace(': MeshPart','').replace('): string',')').replace('): any',')').replace(': any)',')').replace(': boolean?', '')
            geom=re.sub(r'([\w.]+) ([+\-/])= (.+)',r'\1 = \1 \2 \3',geom)
            defs=(COMBAT/'HitboxAssetDefinitions.luau').read_text(encoding='utf-8')
            defs=re.sub(r'([\w.]+) \+= (.+)',r'\1 = \1 + \2',defs)
            gp=Path(td)/'geometry.lua';gp.write_text(geom,encoding='utf-8')
            dp=Path(td)/'defs.lua';dp.write_text(defs,encoding='utf-8')
            subprocess.run([lua,str(ROOT/'system/verify/hitbox_asset_m649.lua'),str(gp),str(dp)],check=True,timeout=15)

    def test_lookup_precedes_geometry_and_records_do_not_retain_vertices(self):
        service=(COMBAT/'EntityHitboxService.luau').read_text(encoding='utf-8')
        builder=(COMBAT/'HitboxDefinitionBuilder.luau').read_text(encoding='utf-8')
        self.assertLess(service.index('HitboxAssetDefinitions.SessionLookup(binding, key, sig)'),service.index('HitboxMeshGeometryCache.Read(meshPart)'))
        self.assertLess(service.index('HitboxAssetDefinitions.Lookup(binding, key, sig)'),service.index('HitboxMeshGeometryCache.Read(meshPart)'))
        self.assertIn('HitboxMeshGeometryCache.Release(geometry)',service)
        self.assertIn('record.geometry = nil',service)
        self.assertNotIn('record.preparedVertices',builder)
        self.assertIn('ipairs(prepareRecord(record))',builder)
        self.assertIn('CombatHitboxDefinitionSource',service)
