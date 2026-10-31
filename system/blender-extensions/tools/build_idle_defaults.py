from pathlib import Path
import json
root=Path(__file__).resolve().parents[3]
data=json.loads((root/'assets/authoring/animations/human_male/idle_runtime_source.json').read_text(encoding='utf8'))
from sys import path
path.insert(0,str(root/'system/control-center'))
from animation_core.registry import lua_data
text='''--!strict
-- Generated from Blender face_idle, 30 FPS. Offset is in face_head space,
-- normalized by eye separation; no mesh IDs, bone counts or cloud upload.
local document = %s
local samples = {
%s
}
local Idle = {document = table.freeze(document)}
function Idle.Offset(time: number): Vector3
    local phase=time%%document.duration
    local low,high=1,#samples
    while high-low>1 do
        local middle=math.floor((low+high)/2)
        if samples[middle][1]<=phase then low=middle else high=middle end
    end
    local a,b=samples[low],samples[high]
    return a[2]:Lerp(b[2],math.clamp((phase-a[1])/(b[1]-a[1]),0,1))
end
return table.freeze(Idle)
'''%(lua_data(data['document']), '\n'.join('    {%.8f,Vector3.new(%.8f,%.8f,%.8f)},'%tuple(row) for row in data['gaze']))
target=root/'src/shared/character/FaceIdleDefaults.luau';target.write_text(text,encoding='utf8')
print('Generated',target.name,len(data['gaze']),'samples')
