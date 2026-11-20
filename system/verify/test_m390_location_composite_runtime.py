"""M390: a rig/effect-bearing Location asset must be compiled as visual-only.

The server-owned carrier, Fire, lights, animated Bone paths and joint identity
are preserved; the client has one shared LOD scheduler, not a second streamer.
"""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'system'/'control-center'))
from services.location_runtime_build import RuntimePlaceBuilder, placement_shape_problem
from services.location_streaming_config import DEFAULT_SETTINGS

CFRAME=[0,3,4,1,0,0,0,1,0,0,0,1]
AXES='X Y Z R00 R01 R02 R10 R11 R12 R20 R21 R22'.split()


def item(parent, klass, name, ref):
    obj=ET.SubElement(parent,'Item',{'class':klass,'referent':ref})
    ET.SubElement(ET.SubElement(obj,'Properties'),'string',name='Name').text=name
    return obj


def mesh(parent, name, ref, mesh_id):
    node=item(parent,'MeshPart',name,ref)
    props=node.find('Properties')
    cf=ET.SubElement(props,'CoordinateFrame',name='CFrame')
    for k,x in zip(AXES,CFRAME):ET.SubElement(cf,k).text=str(x)
    size=ET.SubElement(props,'Vector3',name='size')
    for k,x in zip('XYZ',(2,2,2)):ET.SubElement(size,k).text=str(x)
    ET.SubElement(ET.SubElement(props,'Content',name='MeshContent'),'uri').text='rbxassetid://'+mesh_id
    for key in ('CanCollide','CanTouch','CanQuery','CastShadow'):
        ET.SubElement(props,'bool',name=key).text='true' if key=='CastShadow' else 'false'
    return node


def snapshot(root):
    result=[]
    def visit(n,parent=None):
        ix=len(result)+1
        row={'id':ix,'parent':parent,'class':n.get('class'),'name':next((x.text for x in n.findall('./Properties/string') if x.get('name')=='Name'),'')}
        if row['class'] in ('MeshPart','Part'):
            row.update(cframe=list(CFRAME),size=[2,2,2],canCollide=False,canQuery=False,
                collisionFidelity='Enum.CollisionFidelity.Box')
        if row['class']=='MeshPart':
            contents=n.findall('./Properties/Content')
            row['meshId']=(contents[0].findtext('uri') or '').split('//')[-1]
        result.append(row)
        for ch in n:
            if ch.tag=='Item':visit(ch,ix)
    visit(root)
    return result


class CompositeRuntime(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)
        (self.path/'place').mkdir()
        tree=ET.Element('roblox',version='4')
        workspace=item(tree,'Workspace','Workspace','WS')
        item(tree,'ReplicatedStorage','ReplicatedStorage','RS')
        location=item(workspace,'Model','statue_01__unit01','MODEL')
        carrier=mesh(location,'rig_carrier','RIG','80001')
        bone=item(carrier,'Bone','root','BONE')
        socket=item(bone,'Attachment','lantern_01_socket','SOCKET')
        item(socket,'PointLight','PointLight','LIGHT')
        item(socket,'Fire','Fire','FLAME')
        item(socket,'ParticleEmitter','smoke','SMOKE')
        self.parts=[]
        for index in range(3):
            visual=mesh(location,['statue_01','statue_01_pedestal','statue_01_sword'][index],
                f'VISUAL{index}',str(85001+index))
            item(visual,'Weld','LocationSkinWeld',f'WELD{index}')
            self.parts.append(visual)
        controller=item(location,'AnimationController','AnimationController','CTRL')
        item(controller,'Animator','Animator','ANIM')
        self.rows=[{'slug':'statue_01','path':'Workspace.statue_01__unit01',
            'placementId':'A123', 'meshId':'85001', 'hierarchy':snapshot(location),
            'pivotEvidence':{'modelPivot':list(CFRAME)},'issues':[],
            'duplicateId':False,'ambiguous':False}]
        self.source=self.path/'place'/'game1_runtime_source.rbxlx'
        ET.ElementTree(tree).write(self.source,encoding='utf-8',xml_declaration=True)
        self.settings=copy.deepcopy(DEFAULT_SETTINGS)
        self.settings['modes']={'statue_01':'full'}

    def compile(self):
        compiler=RuntimePlaceBuilder(self.path)
        check=compiler.inspect(self.rows,self.settings)
        build=compiler.prepare(self.rows,expected_sha=check['sourceSha256'],
            snapshot_id=160,catalog_digest='test',settings=self.settings)
        return ET.parse(build['runtimePath']),build

    def test_effects_carrier_and_joints_survive_and_mesh_content_does_not(self):
        self.assertEqual(placement_shape_problem(self.rows[0]),'')
        runtime,build=self.compile()
        classes=[x.get('class') for x in runtime.iter('Item')]
        self.assertEqual(classes.count('MeshPart'),1) # technical rig only
        self.assertEqual(classes.count('Part'),3) # three visual proxies
        for klass in ('Bone','Attachment','PointLight','Fire','ParticleEmitter',
                      'Weld','Animator','AnimationController'):
            self.assertIn(klass,classes)
        self.assertEqual(build['removedVisualMeshParts'],3)
        self.assertEqual(self.source.read_bytes(),Path(build['backupPath']).read_bytes())
        self.assertFalse(build['publishAllowed'])
        self.assertFalse(any('MeshContent' in str(p.attrib)
            for n in runtime.iter('Item') if n.get('class')=='Part'
            for p in n.findall('./Properties/*')))

    def test_manifest_carries_each_visual_id_and_model_path(self):
        runtime,_=self.compile()
        marker=next(n for n in runtime.iter('Item') if n.get('class')=='StringValue')
        manifest=json.loads(next(p.text for p in marker.findall('./Properties/string') if p.get('name')=='Value'))
        row=manifest['placements'][0]
        self.assertEqual(row['modelPath'],['statue_01__unit01'])
        self.assertEqual(len(row['components']),3)
        self.assertEqual({part['meshId'] for part in row['components']},{'85001','85002','85003'})

    def test_unsafe_collision_shape_rejected(self):
        self.rows[0]['hierarchy'][-6]['collisionFidelity']='Enum.CollisionFidelity.PreciseConvexDecomposition'
        # Explicitly mark the first true visual collidable to exercise the guard.
        body=next(x for x in self.rows[0]['hierarchy'] if x['name']=='statue_01')
        body['canCollide']=True
        body['collisionFidelity']='Enum.CollisionFidelity.PreciseConvexDecomposition'
        self.assertIn('Box fidelity',placement_shape_problem(self.rows[0]))

    def test_stale_effect_or_skeleton_snapshot_rejected(self):
        self.rows[0]['hierarchy']=[r for r in self.rows[0]['hierarchy'] if r['name']!='Fire']
        with self.assertRaisesRegex(ValueError,'hierarchy differs from Scan'):
            RuntimePlaceBuilder(self.path).inspect(self.rows,self.settings)

    def test_existing_shared_client_owner_uses_no_separate_scheduler(self):
        client=(ROOT/'src/client/world/LocationWorldStreamer.luau').read_text()
        adapter=(ROOT/'src/client/world/LocationCompositeVisual.luau').read_text()
        server=(ROOT/'src/server/world/LocationLodTemplateService.luau').read_text()
        self.assertIn('LocationCompositeVisual.Create',client)
        self.assertNotIn('RunService.Heartbeat',adapter)
        self.assertNotIn('RenderStepped',adapter)
        self.assertIn('Game1VisualProxyWeld',adapter)
        self.assertIn('MeshPhysics.IsLocationCarrier',server)

if __name__=='__main__':unittest.main()
