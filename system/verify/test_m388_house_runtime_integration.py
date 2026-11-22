"""M388: Real Estate draft extraction, Plot binding, physics/socket ownership and shared Runtime contract."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'system/control-center'))
from services.location_runtime_build import RuntimePlaceBuilder
from services.house_runtime_compilation import inspect, payload, transform
from services.location_runtime_build import _runtime_payload

FRAME=[10,20,30,1,0,0,0,1,0,0,0,1]


def item(parent,name,cls,ref):
    node=ET.SubElement(parent,'Item',{'class':cls,'referent':ref})
    ET.SubElement(ET.SubElement(node,'Properties'),'string',name='Name').text=name
    return node


def basepart(parent,name,cls,ref,cf=FRAME,mesh=None,collide=False):
    node=item(parent,name,cls,ref)
    props=node.find('Properties')
    frame=ET.SubElement(props,'CoordinateFrame',name='CFrame')
    for axis,val in zip(('X','Y','Z','R00','R01','R02','R10','R11','R12','R20','R21','R22'),cf):
        ET.SubElement(frame,axis).text=str(val)
    size=ET.SubElement(props,'Vector3',name='size')
    for axis,val in zip('XYZ',(5,6,7)):
        ET.SubElement(size,axis).text=str(val)
    ET.SubElement(props,'bool',name='CanCollide').text=str(collide).lower()
    if mesh: ET.SubElement(ET.SubElement(props,'Content',name='MeshContent'),'uri').text=f'rbxassetid://{mesh}'
    return node


def build_source(path):
    root=ET.Element('roblox',version='4')
    ws=item(root,'Workspace','Workspace','RBX_WS')
    item(root,'ReplicatedStorage','ReplicatedStorage','RBX_RS')
    plots=item(ws,'Plots','Folder','RBX_PLOTS')
    plot=item(plots,'01','Folder','RBX_PLOT')
    houses=item(plot,'Houses','Folder','RBX_HOUSES')
    house=item(houses,'house_level5_01','Model','RBX_HOUSE')
    model_pivot=ET.SubElement(house.find('Properties'), 'OptionalCoordinateFrame', name='WorldPivotData')
    pivot_frame=ET.SubElement(model_pivot,'CFrame')
    for key,value in zip(('X','Y','Z','R00','R01','R02','R10','R11','R12','R20','R21','R22'),FRAME):
        ET.SubElement(pivot_frame,key).text=str(value)
    static=item(house,'StaticAssembly','Model','RBX_STATIC')
    carrier=basepart(static,'rig_carrier','MeshPart','RBX_CARRIER',mesh='900')
    item(carrier,'house_floor_01_spawn_socket','Bone','RBX_SOCKET')
    visual=basepart(static,'window_frames_glass','MeshPart','RBX_GLASS',mesh='901')
    ET.SubElement(visual.find('Properties'),'string',name='TextureID').text='rbxassetid://999'
    door=item(house,'DoorAssembly','Model','RBX_DOOR_ASSEMBLY')
    rig=item(door,'DoorRig','Model','RBX_DOOR_RIG')
    moving=basepart(rig,'door','MeshPart','RBX_DOOR_PART',mesh='902',collide=True)
    item(moving,'door_01_hinge_socket','Bone','RBX_HINGE')
    ET.SubElement(door.find('Properties'),'Ref',name='PrimaryPart').text='RBX_DOOR_PART'
    ET.SubElement(house.find('Properties'),'Ref',name='PrimaryPart').text='RBX_CARRIER'
    # Separate COLLISION Part remains in authored/runtime Workspace.
    basepart(house,'__Game1Collision_wall','Part','RBX_COLL')
    path.parent.mkdir(parents=True,exist_ok=True)
    ET.ElementTree(root).write(path,encoding='utf-8',xml_declaration=True)
    return path


def selected():
    return {'house_level5_01':{
        'house':{'slug':'house_level5_01','status':'PUBLISHED','meshParts':['window_frames_glass','door'],
            'meshOptions':{
                'window_frames_glass':{'appearanceMode':'material_atlas','visualMaterial':'ForceField',
                    'visualColor':'#CECECE','noCollide':True,'collisionFidelity':'Box',
                    'alphaEnabled':False,'doubleSided':True,'destructible':False,
                    'distanceStreaming':True,'loadDistanceStuds':50},
                'door':{'appearanceMode':'material','visualMaterial':'Wood','visualColor':'#886633',
                    'noCollide':False,'collisionFidelity':'Box','alphaEnabled':False,
                    'doubleSided':False,'destructible':False,'distanceStreaming':False}},
            'textures':{'window_frames_glass':{'assetId':'999'},'door':{'assetId':''}},
            'partLod1':{part:{'status':'PUBLISHED','modelAssetId':'990'} for part in ('window_frames_glass','door')},
            'partStreaming':{'window_frames_glass':{'lod1':50,'hide':400,'revision':1},
                            'door':{'lod1':150,'hide':400,'revision':1}}},
        'profile':{'mode':'lod1'},
        'placements':[{'plotIndex':1,'worldCFrame':FRAME,'scale':1.0,'revision':7}]
    }}


class HouseRuntimeIntegration(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.source=build_source(self.root/'place/game1_runtime_source.rbxlx')
        self.inputs=selected()

    def test_house_only_runtime_build_removes_all_visual_meshes_but_not_sockets_door_or_collision(self):
        builder=RuntimePlaceBuilder(self.root)
        source_bytes=self.source.read_bytes()
        inspected=builder.inspect([],house_inputs=self.inputs)
        self.assertEqual(inspected['houseCount'],1)
        self.assertEqual(inspected['houseMeshParts'],2)
        result=builder.prepare([],expected_sha=inspected['sourceSha256'],snapshot_id=77,
                               catalog_digest='test',house_inputs=self.inputs)
        self.assertEqual(self.source.read_bytes(),source_bytes)
        self.assertEqual(Path(result['backupPath']).read_bytes(),source_bytes)
        self.assertEqual(result['convertedHouseVisualMeshParts'],2)
        self.assertEqual(result['housePlacements'],1)
        tree=ET.parse(result['runtimePath'])
        nodes={n.get('referent'):n for n in tree.iter('Item')}
        self.assertEqual(nodes['RBX_GLASS'].get('class'),'Part')
        self.assertEqual(nodes['RBX_DOOR_PART'].get('class'),'Part')
        self.assertEqual(nodes['RBX_CARRIER'].get('class'),'MeshPart')
        self.assertEqual(nodes['RBX_COLL'].get('class'),'Part')
        self.assertEqual(nodes['RBX_HINGE'].get('class'),'Bone')
        self.assertEqual(nodes['RBX_SOCKET'].get('class'),'Bone')
        self.assertEqual(nodes['RBX_DOOR_ASSEMBLY'].get('class'),'Model')
        self.assertEqual(nodes['RBX_DOOR_ASSEMBLY'].find("./Properties/Ref[@name='PrimaryPart']").text,'RBX_DOOR_PART')
        manifest=json.loads(next(n.find("./Properties/string[@name='Value']").text for n in tree.iter('Item')
            if n.get('class')=='StringValue'))
        self.assertEqual(manifest['schemaVersion'],4)
        self.assertFalse(manifest['publishAllowed'])
        self.assertEqual(manifest['houses']['types']['house_level5_01']['parts'][0]['meshId'],'902')
        self.assertEqual(manifest['houses']['types']['house_level5_01']['parts'][1]['lod1From'],50)
        self.assertEqual(manifest['houses']['types']['house_level5_01']['parts'][1]['hideFrom'],400)
        self.assertNotIn('lod1',manifest['houses']['types']['house_level5_01'])
        self.assertNotIn('parts',manifest['houses']['placements'][0])

    def test_plot_registration_does_not_rewrite_saved_house_or_relax_mesh_validation(self):
        tree=ET.parse(self.source)
        inputs=copy.deepcopy(self.inputs)
        inputs['house_level5_01']['placements'][0]['worldCFrame'][0]+=5
        found=inspect(tree,inputs)
        self.assertEqual(found[0]['pivot'],FRAME)
        inputs=copy.deepcopy(self.inputs)
        inputs['house_level5_01']['house']['meshParts'].append('floor')
        inputs['house_level5_01']['house']['partStreaming']['floor']={'lod1':150,'hide':400,'revision':0}
        inputs['house_level5_01']['house']['partLod1']['floor']={'status':'PUBLISHED','modelAssetId':'990'}
        with self.assertRaisesRegex(ValueError,'mismatch'):
            inspect(tree,inputs)

    def test_registered_author_anchor_offset_matches_rig_without_changing_model_pivot(self):
        tree=ET.parse(self.source)
        inputs=copy.deepcopy(self.inputs)
        inputs['house_level5_01']['placements'][0]['houseAnchorLocalCFrame']=[3,4,5,1,0,0,0,1,0,0,0,1]
        carrier=next(n for n in tree.iter('Item') if n.get('referent')=='RBX_CARRIER')
        for axis,val in zip(('X','Y','Z'),(13,24,35)):
            carrier.find("./Properties/CoordinateFrame[@name='CFrame']/"+axis).text=str(val)
        # The carrier differs, but the Model pivot still matches Plot 01.
        found=inspect(tree,inputs)
        self.assertEqual(found[0]['plotIndex'],1)
        self.assertEqual(found[0]['pivot'],FRAME)

    def test_compact_39_plot_manifest_does_not_repeat_mesh_metadata(self):
        base=inspect(ET.parse(self.source),self.inputs)[0]
        rows=[]
        for index in range(39):
            new=copy.deepcopy(base)
            new['plotIndex']=index+1
            new['pivot'][0]+=index*100
            new['parts']=copy.deepcopy(base['parts'])
            for visual in new['parts']:
                visual['cframe'][0]+=index*100
            new['path'][-2]=f'plot_{index+1:02}'
            rows.append(new)
        houses=payload(rows,self.inputs)
        self.assertEqual(len(houses['placements']),39)
        self.assertEqual(len(houses['types']['house_level5_01']['parts']),2)
        self.assertNotIn('parts',houses['placements'][1])
        envelope=_runtime_payload([],snapshot_id=1,catalog_digest='test',houses=houses)
        self.assertLess(len(json.dumps(envelope,separators=(',',':'))),180000)
        rows[1]['parts'][1]['cframe'][0] += 3
        with self.assertRaisesRegex(ValueError,'inconsistent authored transforms'):
            payload(rows,self.inputs)

    def test_invalid_collidable_precise_mesh_refused_before_modification(self):
        tree=ET.parse(self.source)
        inputs=copy.deepcopy(self.inputs)
        inputs['house_level5_01']['house']['meshOptions']['door']['collisionFidelity']='PreciseConvexDecomposition'
        with self.assertRaisesRegex(ValueError,'Box fidelity'):
            inspect(tree,inputs)
        self.assertEqual(next(n for n in tree.iter('Item') if n.get('referent')=='RBX_DOOR_PART').get('class'),'MeshPart')

    def test_unpublished_alpha_atlas_is_refused(self):
        tree=ET.parse(self.source)
        inputs=copy.deepcopy(self.inputs)
        inputs['house_level5_01']['house']['textures']['window_frames_glass']['assetId']=''
        with self.assertRaisesRegex(ValueError,'texture'):
            inspect(tree,inputs)

    def test_one_shared_client_scheduler_and_one_global_budget(self):
        client=(ROOT/'src/client/world/LocationWorldStreamer.luau').read_text(encoding='utf-8')
        helper=(ROOT/'src/client/world/HouseVisualAdapter.luau').read_text(encoding='utf-8')
        self.assertIn('houseAdapter:Resolve(cameraPosition)',client)
        self.assertIn('houseAdapter:Step(MAX_CHANGES_PER_TICK // 2)',client)
        self.assertIn('houseAdapter:Step(MAX_CHANGES_PER_TICK - changes)',client)
        self.assertNotIn('RunService.Heartbeat',helper)
        self.assertNotIn('RenderStepped:Connect',helper)
        self.assertIn('MAX_PENDING = 4',helper)
        self.assertIn('visual.generation == ticket',helper)
        self.assertIn('InsertService.CreateMeshPartAsync',helper)
        self.assertIn('Policy.ResolveHouse',helper)
        self.assertIn('Game1HouseClientVisuals',helper)
        self.assertNotIn('LoadAssetAsync',helper)
        self.assertNotIn('RemoteEvent',helper)

if __name__=='__main__': unittest.main()
