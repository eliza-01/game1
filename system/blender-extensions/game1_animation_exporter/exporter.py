"""Blender → native RBXMX + clip event document. No cloud upload or Studio UI."""
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import bpy
from mathutils import Matrix

SWAP=Matrix(((1,0,0,0),(0,0,1,0),(0,1,0,0),(0,0,0,1)))
PRIORITIES={'Idle':0,'Movement':1,'Action':2,'Action2':3,'Action3':4,'Action4':5,'Core':1000}
EVENTS={'blink','face_state','face_reset','eyes_set','eyes_spin_start','eyes_spin_stop'}

def native_matrix(v):
    return Matrix(((v[3],v[4],v[5],v[0]),(v[6],v[7],v[8],v[1]),(v[9],v[10],v[11],v[2]),(0,0,0,1)))

def property_node(properties,kind,name,value):
    node=ET.SubElement(properties,kind,{'name':name});node.text=str(value);return node

def item(parent,kind,name):
    node=ET.SubElement(parent,'Item',{'class':kind});props=ET.SubElement(node,'Properties')
    property_node(props,'string','Name',name);return node,props

def pose(parent,name,matrix,weight):
    node,props=item(parent,'Pose',name)
    property_node(props,'float','Weight',weight)
    property_node(props,'token','EasingStyle',0);property_node(props,'token','EasingDirection',1)
    cf=ET.SubElement(props,'CoordinateFrame',{'name':'CFrame'})
    for key,value in zip(('X','Y','Z'),matrix.translation):ET.SubElement(cf,key).text=format(value,'.10g')
    for i in range(3):
        for j in range(3):ET.SubElement(cf,f'R{i}{j}').text=format(matrix[i][j],'.10g')
    return node

def marker_events(action,start,end,fps):
    events=[]
    for index,marker in enumerate(action.pose_markers):
        label=re.sub(r'\.\d{3}$','',marker.name)
        name,sep,raw=label.partition('|')
        if name not in EVENTS:raise ValueError('Unknown event marker: '+marker.name)
        if not start<=marker.frame<=end:raise ValueError('Marker outside clip: '+marker.name)
        parameters=json.loads(raw) if sep else {}
        if not isinstance(parameters,dict):raise ValueError('Marker parameters must be a JSON object')
        events.append(dict(id=f'event_{index+1:04d}',frame=marker.frame,time=(marker.frame-start)/fps,name=name,parameters=parameters))
    return sorted(events,key=lambda event:event['time'])

def action_slot(action,rig):
    slots=[s for s in action.slots if s.target_id_type=='OBJECT']
    return next((s for s in slots if s.identifier=='OB'+rig.name),slots[0] if slots else None)

def export_clip_steps(rig,action,directory,character_id,bind_file):
    """Yield after each sampled frame so the UI operator can remain responsive."""
    if not re.fullmatch('[a-z][a-z0-9_]*',character_id):raise ValueError('Invalid character ID')
    stem=str(action.get('game1_export_stem',''))
    if not re.fullmatch('[a-z0-9][a-z0-9_]*',stem):raise ValueError('Prepare semantic binding for '+action.name)
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    scene=bpy.context.scene;fps=scene.render.fps/scene.render.fps_base
    start=int(action.get('game1_frame_start',action.frame_range[0]));end=int(action.get('game1_frame_end',action.frame_range[1]))
    if end<=start or end-start>108000:raise ValueError('Invalid clip frame range')
    procedural=action.get('game1_execution')=='procedural'
    native=directory/(character_id+'_'+stem+'.rbxmx')
    document=dict(schema_version=1,clip_name=stem,source_action=action.name,fps=fps,frame_start=start,frame_end=end,
        looped=bool(action.get('game1_looped',False)),mode='procedural' if procedural else 'skeletal',
        events=marker_events(action,start,end,fps))
    if procedural:
        path=native.with_suffix('.animation.json');temporary=path.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(document,indent=2),encoding='utf8');temporary.replace(path)
        yield dict(done=True,animation=None,document=str(path));return
    engine=json.loads(Path(bind_file).read_text(encoding='utf8'))
    bind={b['name']:native_matrix(b['world_cframe']) for b in engine['bones']}
    parents={b['name']:b['parent'] for b in engine['bones']}
    if set(bind)!=set(rig.data.bones.keys()):raise ValueError('Published rig bind does not match current bone names')
    for b in engine.get('source_bones',[]):
        actual=rig.matrix_world@rig.data.bones[b['name']].matrix_local
        if max(abs(actual[i][j]-b['matrix'][i*4+j]) for i in range(4) for j in range(4))>1e-4:
            raise ValueError('Published rig bind changed: '+b['name'])
    active=set()
    slot=action_slot(action,rig)
    if not slot:raise ValueError('Action has no rig slot')
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                if bag.slot_handle!=slot.handle:continue
                for fc in bag.fcurves:
                    match=re.fullmatch(r'pose.bones\["([^"]+)"\]\.(location|rotation_euler|rotation_quaternion)',fc.data_path)
                    if match and match[1] in bind:active.add(match[1])
                    if fc.data_path.endswith('.scale') and any(abs(k.co.y-1)>1e-6 for k in fc.keyframe_points):
                        raise ValueError('Animated bone scale requires a runtime event: '+fc.data_path)
    if not active:raise ValueError('No bone motion; mark this Action as procedural')
    if action.get('game1_scope')=='emotions' and active-{'face_eye_l','face_eye_r','face_brow_l','face_brow_r'}:
        raise ValueError('Emotion clip contains body channels')
    root=ET.Element('roblox',{'version':'4'});sequence,props=item(root,'KeyframeSequence',stem)
    property_node(props,'bool','Loop',str(document['looped']).lower())
    property_node(props,'token','Priority',PRIORITIES.get(str(action.get('game1_priority','Action2')),3))
    carrier=native_matrix(engine['carrier_cframe'])
    old_action=rig.animation_data.action if rig.animation_data else None
    old_slot=rig.animation_data.action_slot if rig.animation_data else None
    old_frame=scene.frame_current
    old_pose={p.name:p.matrix_basis.copy() for p in rig.pose.bones}
    muted=[(track,track.mute) for track in rig.animation_data.nla_tracks] if rig.animation_data else []
    rest={b.name:rig.matrix_world@b.matrix_local for b in rig.data.bones}
    try:
        rig.animation_data_create();rig.animation_data.action=None
        for p in rig.pose.bones:p.matrix_basis=Matrix.Identity(4)
        for track,previous in muted:track.mute=True
        rig.animation_data.action=action;rig.animation_data.action_slot=slot
        for frame in range(start,end+1):
            scene.frame_set(frame)
            posed={name:SWAP@(rig.matrix_world@rig.pose.bones[name].matrix@rest[name].inverted())@SWAP@bind[name] for name in bind}
            key,kprops=item(sequence,'Keyframe',f'frame_{frame}')
            property_node(kprops,'float','Time',(frame-start)/fps)
            carrier_pose=pose(key,'rig_carrier',Matrix.Identity(4),0)
            poses={}
            def ensure(name):
                if name in poses:return poses[name]
                parent=parents[name]
                before=bind[parent] if parent else carrier;after=posed[parent] if parent else carrier
                transform=(before.inverted()@bind[name]).inverted()@after.inverted()@posed[name]
                poses[name]=pose(ensure(parent) if parent else carrier_pose,name,transform,1 if name in active else 0)
                return poses[name]
            for name in sorted(active):ensure(name)
            yield dict(frame=frame,end=end)
    finally:
        rig.animation_data.action=old_action
        if old_action:rig.animation_data.action_slot=old_slot
        for track,previous in muted:track.mute=previous
        scene.frame_set(old_frame)
        for name,basis in old_pose.items():rig.pose.bones[name].matrix_basis=basis
        bpy.context.view_layer.update()
    raw=ET.tostring(root,encoding='utf-8',xml_declaration=True)
    if len(raw)>20*1024*1024:raise ValueError('Native animation exceeds 20 MiB')
    temporary=native.with_suffix('.rbxmx.tmp');temporary.write_bytes(raw);temporary.replace(native)
    document.update(animation_file=native.name,animation_sha256=hashlib.sha256(raw).hexdigest(),
        rig=dict(id=engine['rig_id'],revision=engine['rig_revision'],asset_id=engine['asset_id']))
    path=native.with_suffix('.animation.json');temporary=path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(document,indent=2),encoding='utf8');temporary.replace(path)
    yield dict(done=True,animation=str(native),document=str(path),bones=len(active))
