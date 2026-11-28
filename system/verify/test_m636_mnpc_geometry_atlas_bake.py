"""Shared capture-to-bake contracts; actual SQLite/Pillow; native Blender optional."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
import test_m633_mnpc_lod_authoring as m633
import test_m635_mnpc_assembly_capture as m635
from services import mnpc_lod_bake as bake, mnpc_lod_capture as capture
from services.model_lod_common import sha256
from api.write_world import route
from blender_runtime import blender_executable


def piece(path, shift=0):
    return dict(path=path,vertices=[[shift,0,0],[shift+1,0,0],[shift,1,0],[shift,0,1]],
        uvs=[[0,0],[1,0],[0,1],[1,1]],
        triangles=[[1,3,2,1,3,2],[1,2,4,1,2,4],[1,4,3,2,4,3],[2,3,4,2,3,4]],
        tint=[1,1,1],alphaMode='Texture')


def response(command):
    raw=m635.response(command)
    raw['geometry']=[piece(m['path'],i*2) for i,m in enumerate(raw['meshes'])]
    for m in raw['meshes']:
        if m['owner']!='body':m['textureId']='902'
    return raw


class Bake(unittest.TestCase):
    setUp=m633.MnpcAuthoring.setUp
    new_owner=m633.MnpcAuthoring.new_owner
    payload=m633.MnpcAuthoring.payload
    stage=m633.MnpcAuthoring.stage
    animations=m635.Capture.animations
    cloud=m633.MnpcAuthoring.cloud
    staged=m633.MnpcAuthoring.staged

    def textures(self):
        self.body=self.root/'body.png'; self.weapon=self.root/'weapon.png'
        # Non-symmetric texture proves V flip and remapping, not just color.
        image=Image.new('RGBA',(32,32),(220,0,0,255));image.paste((0,0,220,255),(0,16,32,32));image.save(self.body)
        Image.new('RGBA',(32,16),(0,220,0,255)).save(self.weapon)
        for rows,path,asset in ((self.monsters,self.body,'901'),(self.npcs,self.body,'901'),(self.weapons,self.weapon,'902')):
            for row in rows.rows.values():
                row['textures']=[dict(slot='body',asset_id=asset,sha256=sha256(path),source_path=path.name)]

    def capture(self,kind,anim):
        r=self.owner.describe(kind,'same')
        return capture.capture(self.owner,kind,'same',dict(expectedRevision=r['revision'],fullFingerprint=r['fullFingerprint'],phase=.35,includeGeometry=True),anim,bridge=response)

    def request(self,kind,info):
        r=self.owner.describe(kind,'same')
        return dict(expectedRevision=r['revision'],fullFingerprint=r['fullFingerprint'],captureSha256=info['captureSha256'],targetTriangles=1000,textureSize=128)

    def worker(self,root,script,args,**kwargs):
        self.assertEqual(script,'bake_mnpc_lod_fbx.py')
        data=json.loads(args[0].read_text()); self.assertEqual(len(data['faces']),len(data['faceUV']))
        self.assertEqual(data['vertices'][2],[0,0,1]);self.assertEqual(data['vertices'][3],[0,-1,0])
        self.assertEqual(data['faces'][0],[0,2,1]);self.assertTrue(all(0<=a<=1 for uv in data['faceUV'] for v in uv for a in v))
        args[1].write_bytes(b'; FBX 7.4.0\nFBXHeaderExtension: {}\n'+json.dumps(data,sort_keys=True).encode())
        return {**m633.REPORT,'vertices':len(data['vertices']),'triangles':len(data['faces'])}

    def test_shared_capture_bake_stage_and_idempotence(self):
        self.textures()
        for kind in ('monster','npc'):
            with self.subTest(kind=kind),patch.object(bake,'run_report',side_effect=self.worker):
                anim=self.animations(kind);info=self.capture(kind,anim)
                self.assertTrue(info['geometryReady']); self.assertEqual(info['triangleCount'],4 if kind=='monster' else 8)
                self.assertEqual(info,capture.summary(self.new_owner(),kind,'same',anim))
                status,row=route(f'/api/lod-manager/mnpc/{kind}/same/bake',lambda:self.request(kind,info),{'mnpc_lod':self.owner,kind+'_animations':anim})
                self.assertEqual(status,200,row);self.assertEqual(row['status'],'STAGED');self.assertFalse(row['runtimeReady'])
                recipe=row['geometry']['preparation'];self.assertEqual(recipe['mode'],'captured_idle');self.assertEqual(recipe['materialTiles'],1 if kind=='monster' else 2)
                atlas=self.atlases.get_variant(row['atlasVariantId'])
                with Image.open(self.root/atlas['source_path']) as image:
                    self.assertEqual(image.size,(128,128));self.assertEqual(image.getpixel((2,2)),(220,0,0,255))
                    self.assertEqual(image.getpixel((2,33)),(0,0,220,255));self.assertEqual(image.getpixel((0,0)),(220,0,0,255))
                    if kind=='npc':self.assertEqual(image.getpixel((66,2)),(0,220,0,255))
                self.assertEqual(bake.bake(self.owner,kind,'same',self.request(kind,info),anim)['revision'],1)
                self.assertEqual(len(self.owner.history(kind,'same')),1)
        self.inspect.assert_not_called()

    def test_atlas_corner_uv_and_dedup(self):
        self.textures();raw=response({'kind':'npc','equipment':{'right':{}}})
        sources={('body','901'):(self.body,sha256(self.body)),('right','902'):(self.weapon,sha256(self.weapon))}
        dst=self.root/'atlas.png';data,count,tiles=bake.assemble(raw,sources,128,dst)
        self.assertEqual((count,tiles),(8,2))
        with Image.open(dst) as img:
            def pixel(uv):return img.getpixel((int(uv[0]*128),int((1-uv[1])*128)))
            self.assertEqual(pixel(data['faceUV'][0][0]),(220,0,0,255))
            self.assertEqual(pixel(data['faceUV'][0][1]),(0,0,220,255))
            self.assertEqual(pixel(data['faceUV'][4][0]),(0,220,0,255))
        sources['right','902']=sources['body','901']
        data,count,tiles=bake.assemble(raw,sources,128,dst);self.assertEqual(tiles,1)
        self.assertEqual(data['faceUV'][0],data['faceUV'][4])
        raw['geometry'][1]['tint']=[.5,1,1]
        data,count,tiles=bake.assemble(raw,sources,128,dst);self.assertEqual(tiles,2)

    def test_invalid_geometry_and_old_plugin_preserve_capture(self):
        self.textures();anim=self.animations('monster');info=self.capture('monster',anim)
        p=capture._file(self.owner,'monster','same');old=p.read_bytes()
        r=self.owner.describe('monster','same')
        req=dict(expectedRevision=r['revision'],fullFingerprint=r['fullFingerprint'],phase=.35,includeGeometry=True)
        for mutation in (lambda a:a.pop('geometry'), lambda a:a['geometry'][0]['triangles'][0].__setitem__(0,0),lambda a:a['geometry'][0]['uvs'][0].__setitem__(0,2),lambda a:a['geometry'][0].update(path='wrong'),lambda a:a['meshes'][0].update(transparency=.5)):
            def bad(cmd):
                raw=response(cmd);mutation(raw);return raw
            with self.assertRaises(ValueError):capture.capture(self.owner,'monster','same',req,anim,bridge=bad)
            self.assertEqual(p.read_bytes(),old)
        self.assertEqual(info,capture.summary(self.owner,'monster','same',anim))

    def test_failed_bake_and_stale_idle_or_texture_preserve_previous_revision(self):
        self.textures();anim=self.animations('monster');prior=self.stage();info=self.capture('monster',anim);req=self.request('monster',info)
        with patch.object(bake,'run_report',side_effect=ValueError('Blender failed')):
            with self.assertRaisesRegex(ValueError,'Blender failed'):bake.bake(self.owner,'monster','same',req,anim)
        def changed(*args,**kwargs):
            result=self.worker(*args,**kwargs);anim.rows[0]['asset_id']='888';return result
        with patch.object(bake,'run_report',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'changed during bake'):bake.bake(self.owner,'monster','same',req,anim)
        anim.rows[0]['asset_id']='543'
        self.body.write_bytes(b'changed')
        with patch.object(bake,'run_report') as worker:
            with self.assertRaisesRegex(ValueError,'texture missing or changed'):bake.bake(self.owner,'monster','same',req,anim)
            worker.assert_not_called()
        r=self.owner.describe('monster','same');self.assertEqual(r['revision'],prior['revision']);self.assertEqual(r['sourceSha256'],prior['sourceSha256'])
        self.assertEqual(len(self.owner.history('monster','same')),1)

    def test_publication_rechecks_idle(self):
        self.textures();anim=self.animations('monster');info=self.capture('monster',anim)
        with patch.object(bake,'run_report',side_effect=self.worker):
            row=bake.bake(self.owner,'monster','same',self.request('monster',info),anim)
        anim.rows[0]['asset_id']='888'
        self.owner.animations={'monster':anim}
        self.assertEqual(self.owner.describe('monster','same')['status'],'IDLE_CHANGED')
        with self.assertRaisesRegex(ValueError,'Baked idle changed'):
            self.owner.publish('monster','same',row['revision'],m633.CREDS,animations=anim)
        self.assertEqual(len(self.owner.history('monster','same')),1)

    def test_native_plugin_boundary(self):
        s=(m633.ROOT/'system/studio-plugin/modules/StudioMnpcGeometryCapture.luau').read_text()
        for t in ('GetVertexBones','GetVertexBoneWeights','GetBoneCFrame','TransformedWorldCFrame','GetFaceUVs','editable:Destroy()','skin bind mismatch'):
            self.assertIn(t,s)
        self.assertNotIn('Instance.new(',s)
        manifest=json.loads((m633.ROOT/'system/studio-plugin/plugin.project.json').read_text())['tree']['modules']
        self.assertIn('StudioMnpcGeometryCapture',manifest)


class Native(unittest.TestCase):
    def test_captured_fbx_roundtrip(self):
        try:blender_executable()
        except RuntimeError:self.skipTest('Blender not installed')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);raw=response({'kind':'monster','equipment':{}})
            tex=root/'body.png';Image.new('RGB',(16,16),'red').save(tex)
            data,_,_=bake.assemble(raw,{('body','901'):(tex,sha256(tex))},128,root/'atlas.png')
            inp=root/'posed.json';inp.write_text(json.dumps(data));out=root/'lod1.fbx';report=root/'report.json'
            g=bake.run_report(m633.ROOT,'bake_mnpc_lod_fbx.py',(inp,out,report,'100'),report_path=report,label='native captured bake',timeout=120)
            self.assertEqual(g['meshes'],1);self.assertEqual(g['armatures'],0);self.assertEqual(g['triangles'],4);self.assertTrue(out.is_file())
