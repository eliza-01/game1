import bpy
from pathlib import Path
from .exporter import export_clip_steps,action_slot

class GAME1_PG_animation_export(bpy.types.PropertyGroup):
    directory: bpy.props.StringProperty(name='Export folder',subtype='DIR_PATH')
    character_id: bpy.props.StringProperty(name='Character ID',default='human_male')
    clip: bpy.props.StringProperty(name='Clip')
    bind_file: bpy.props.StringProperty(name='Published rig bind',subtype='FILE_PATH',default=str(Path(__file__).with_name('engine_bind.json')))

class GAME1_OT_add_blink(bpy.types.Operator):
    bl_idname='game1_animation.add_blink';bl_label='Add blink marker';bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        settings=context.scene.game1_animation_export
        action=bpy.data.actions.get(settings.clip) or (context.object.animation_data.action if context.object and context.object.animation_data else None)
        if not action:self.report({'ERROR'},'Select an Action first');return {'CANCELLED'}
        marker=action.pose_markers.new('blink');marker.frame=context.scene.frame_current
        self.report({'INFO'},f'blink at frame {marker.frame}');return {'FINISHED'}

class GAME1_OT_preview_clip(bpy.types.Operator):
    bl_idname='game1_animation.preview_clip';bl_label='Show selected Action';bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        rig=context.object;settings=context.scene.game1_animation_export
        action=bpy.data.actions.get(settings.clip)
        if not rig or rig.type!='ARMATURE' or not action:self.report({'ERROR'},'Select the rig and an Action');return {'CANCELLED'}
        rig.animation_data_create();rig.animation_data.action=action
        slot=action_slot(action,rig)
        if slot:rig.animation_data.action_slot=slot
        context.scene.frame_start=int(action.get('game1_frame_start',action.frame_range[0]))
        context.scene.frame_end=int(action.get('game1_frame_end',action.frame_range[1]))
        context.scene.frame_set(context.scene.frame_start)
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type=='DOPESHEET_EDITOR':
                    area.spaces.active.dopesheet.show_only_selected=False
                    if hasattr(area.spaces.active,'show_pose_markers'):area.spaces.active.show_pose_markers=True
        if action.get('game1_execution')=='procedural':self.report({'INFO'},'Event timeline; visual state is evaluated in Roblox')
        return {'FINISHED'}

class GAME1_OT_export_clips(bpy.types.Operator):
    bl_idname='game1_animation.export_clips';bl_label='Export animation package'
    all_prepared: bpy.props.BoolProperty(default=False)
    def execute(self,context):
        rig=context.object
        if not rig or rig.type!='ARMATURE':self.report({'ERROR'},'Select the character armature');return {'CANCELLED'}
        settings=context.scene.game1_animation_export
        if not settings.directory:self.report({'ERROR'},'Choose an export folder');return {'CANCELLED'}
        self.rig_name=rig.name
        actions=[a.name for a in bpy.data.actions if a.get('game1_export_stem')] if self.all_prepared else [settings.clip or (rig.animation_data.action.name if rig.animation_data and rig.animation_data.action else '')]
        if not actions or not actions[0]:self.report({'ERROR'},'Select a clip');return {'CANCELLED'}
        self.actions=iter(actions);self.worker=None;self.total=len(actions);self.done=0
        self.directory=bpy.path.abspath(settings.directory);self.character=settings.character_id;self.bind=bpy.path.abspath(settings.bind_file)
        self.timer=context.window_manager.event_timer_add(.02,window=context.window)
        context.window_manager.modal_handler_add(self);return {'RUNNING_MODAL'}
    def finish(self,context):
        if self.worker:self.worker.close();self.worker=None
        context.window_manager.event_timer_remove(self.timer)
        context.workspace.status_text_set(None)
    def modal(self,context,event):
        if event.type=='ESC':self.finish(context);self.report({'WARNING'},'Export cancelled; completed packages kept');return {'CANCELLED'}
        if event.type!='TIMER':return {'RUNNING_MODAL'}
        try:
            for _ in range(8):
                if self.worker is None:
                    name=next(self.actions,None)
                    if name is None:self.finish(context);self.report({'INFO'},f'Exported {self.done} clip packages');return {'FINISHED'}
                    self.worker=export_clip_steps(bpy.data.objects[self.rig_name],bpy.data.actions[name],self.directory,self.character,self.bind)
                value=next(self.worker,None)
                if value is None:self.worker=None;self.done+=1
                context.workspace.status_text_set(f'Game1 export: {self.done}/{self.total}')
        except Exception as exc:
            self.finish(context);self.report({'ERROR'},str(exc));return {'CANCELLED'}
        return {'RUNNING_MODAL'}

class GAME1_PT_animation_export(bpy.types.Panel):
    bl_label='Animation packages';bl_idname='GAME1_PT_animation_export';bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='Game1'
    def draw(self,context):
        layout=self.layout;settings=context.scene.game1_animation_export
        layout.prop(settings,'character_id');layout.prop_search(settings,'clip',bpy.data,'actions');layout.prop(settings,'directory')
        action=bpy.data.actions.get(settings.clip)
        if action:layout.label(text='Procedural timeline' if action.get('game1_execution')=='procedural' else 'Bone motion + events')
        layout.operator('game1_animation.preview_clip')
        layout.operator('game1_animation.add_blink')
        layout.operator('game1_animation.export_clips',text='Export selected').all_prepared=False
        layout.operator('game1_animation.export_clips',text='Export all prepared').all_prepared=True
        layout.prop(settings,'bind_file')

CLASSES=(GAME1_PG_animation_export,GAME1_OT_add_blink,GAME1_OT_preview_clip,GAME1_OT_export_clips,GAME1_PT_animation_export)
def register():
    for cls in CLASSES:bpy.utils.register_class(cls)
    bpy.types.Scene.game1_animation_export=bpy.props.PointerProperty(type=GAME1_PG_animation_export)
def unregister():
    del bpy.types.Scene.game1_animation_export
    for cls in reversed(CLASSES):bpy.utils.unregister_class(cls)
