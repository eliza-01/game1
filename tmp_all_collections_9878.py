import bpy, json
print(json.dumps({'collections':[c.name for c in bpy.data.collections],
                  'human_named_objects':[o.name for o in bpy.data.objects if 'human' in o.name.lower()]},ensure_ascii=False,indent=2))
