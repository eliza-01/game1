import bpy,json
from pathlib import Path
from mathutils import Matrix,Vector
rig=bpy.data.objects['human_armature'];action=bpy.data.actions['face_idle'];scene=bpy.context.scene
root=Path(__file__).resolve().parents[3]
out=root/'assets/authoring/animations/human_male';out.mkdir(parents=True,exist_ok=True)
bind=json.loads((root/'system/blender-extensions/game1_animation_exporter/engine_bind.json').read_text())
cf=next(b['world_cframe'] for b in bind['bones'] if b['name']=='face_head')
engine_head=Matrix(((cf[3],cf[4],cf[5]),(cf[6],cf[7],cf[8]),(cf[9],cf[10],cf[11])))
names=('face_eye_l','face_eye_r');rest={n:(rig.matrix_world@rig.data.bones[n].matrix_local).translation for n in names}
distance=(rest[names[0]]-rest[names[1]]).length
old_action=rig.animation_data.action;old_slot=rig.animation_data.action_slot;old_frame=scene.frame_current
old_pose={p.name:p.matrix_basis.copy() for p in rig.pose.bones};nla=[(t,t.mute) for t in rig.animation_data.nla_tracks]
values=[]
try:
 rig.animation_data.action=None
 for p in rig.pose.bones:p.matrix_basis=Matrix.Identity(4)
 for t,m in nla:t.mute=True
 rig.animation_data.action=action;rig.animation_data.action_slot=next(s for s in action.slots if s.target_id_type=='OBJECT')
 for frame in range(1,481):
  scene.frame_set(frame);delta=sum(((rig.matrix_world@rig.pose.bones[n].matrix).translation-rest[n] for n in names),Vector())/2
  local=engine_head.inverted()@Vector((delta.x,delta.z,delta.y))/distance
  values.append([(frame-1)/30,*local])
finally:
 rig.animation_data.action=old_action;rig.animation_data.action_slot=old_slot;scene.frame_set(old_frame)
 for t,m in nla:t.mute=m
 for name,m in old_pose.items():rig.pose.bones[name].matrix_basis=m
 bpy.context.view_layer.update()
baseline=values[0][1:]
for row in values:
 for i in range(3):row[i+1]-=baseline[i]
def reduce(rows):
 if len(rows)<3:return rows
 a,b=rows[0],rows[-1];span=b[0]-a[0]
 errors=[sum((r[i]-(a[i]+(b[i]-a[i])*(r[0]-a[0])/span))**2 for i in range(1,4))**.5 for r in rows]
 index=max(range(len(rows)),key=lambda i:errors[i])
 return rows[:1]+rows[-1:] if errors[index]<.00015 else reduce(rows[:index+1])[:-1]+reduce(rows[index:])
reduced=reduce(values)
events=[]
for marker in action.pose_markers:
 name,_,params=marker.name.partition('|')
 if name=='blink':events.append(dict(name=name,frame=marker.frame,time=(marker.frame-1)/30,parameters=json.loads(params) if params else {}))
document=dict(schema_version=1,clip_name='emotions_idle',mode='procedural',fps=30,frame_start=1,frame_end=480,duration=479/30,looped=True,events=events)
(out/'idle_runtime_source.json').write_text(json.dumps(dict(document=document,gaze=reduced,source=bpy.data.filepath),indent=2),encoding='utf8')
print(json.dumps({'samples':len(values),'reduced':len(reduced),'blinks':len(events),'distance':distance}))
