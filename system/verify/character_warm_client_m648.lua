-- Syntax-adapted actual optional client warm runner. No real engine fetch.
local path=arg[1]
table.freeze=function(t)return t end
local time=0; os.clock=function()return time end
task={wait=function(n)time=time+n end}
local source={MeshId='rbxassetid://9',IsA=function(_,name)return name=='MeshPart'end}
local folder={FindFirstChild=function(_,name)if name=='Mesh1' and time>=0.1 then return source end end}
local storage={FindFirstChild=function()return folder end}
game={GetService=function()return storage end}
script={Parent={WaitForChild=function(_,name)return name end}}
local calls,loads=0,0;local current=true;local cancelOnRequest=false;local fail=false
local request={Invoke=function(_,alive,timeout,index)
    calls=calls+1
    if cancelOnRequest then current=false end
    if fail then return true,{ok=false,error='component_unavailable'}end
    return true,{ok=true,meshes={'Mesh1'},images={'rbxassetid://8'},count=2}
end}
local preload={PreloadResources=function(sources,images,alive)
    assert(#sources==1 and sources[1]==source and #images==1 and alive());loads=loads+1;return true
end}
require=function(name)if name=='CharacterCreationRequest'then return request else return preload end end
warn=function()end
local warm=dofile(path)
local function alive()return current end
assert(warm.Run({},alive) and calls==2 and loads==2 and time>=0.1)
current=false;assert(not warm.Run({},alive) and calls==2)
current=true;cancelOnRequest=true;assert(not warm.Run({},alive) and calls==3 and loads==2)
current=true;cancelOnRequest=false;fail=true;assert(not warm.Run({},alive) and calls==4 and loads==2)
current=true;fail=false;time=0;folder.FindFirstChild=function()return nil end
assert(not warm.Run({},alive) and calls==5 and loads==2 and time>=5 and time<5.1)
print('M648 optional client warm cancellation / replica timeout: PASS')
