local geometryPath, definitionPath = arg[1], arg[2]
table.freeze = function(t) return t end
math.round = function(x) return math.floor(x + 0.5) end
local warnings, reads, destroyed = 0, 0, 0
warn = function() warnings = warnings + 1 end
local vector = function(x,y,z) return {X=x,Y=y,Z=z} end
Vector3 = {new=vector}
local function cf(v, yaw)
    yaw = yaw or 0
    local c,s = math.cos(yaw),math.sin(yaw)
    local function inverse(x) return vector(c*x.X-s*x.Z,x.Y,s*x.X+c*x.Z) end
    local result = {Position=v, UpVector=vector(0,1,0), yaw=yaw}
    function result:GetComponents() return v.X,v.Y,v.Z,c,0,s,0,1,0,-s,0,c end
    function result:PointToObjectSpace(x) return inverse(vector(x.X-v.X,x.Y-v.Y,x.Z-v.Z)) end
    function result:VectorToObjectSpace(x) return inverse(x) end
    function result:ToObjectSpace(other) return cf(self:PointToObjectSpace(other.Position),other.yaw-yaw) end
    return result
end
CFrame = {new=cf}
local encodedValues = {}
local function encode(v)
    if type(v) == 'table' then
        local parts = {}
        for _, x in ipairs(v) do parts[#parts+1] = encode(x) end
        return '['..table.concat(parts,',')..']'
    elseif type(v) == 'string' then return string.format('%q',v)
    else return tostring(v) end
end
local editable = {
    GetFaces=function() return {1} end,
    GetFaceVertices=function() return {1,2,1} end,
    GetVertexBones=function() return {4} end,
    GetVertexBoneWeights=function() return {2} end,
    GetBoneName=function() return 'head' end,
    GetBoneCFrame=function() return cf(vector(0,0,0)) end,
    GetPosition=function(_,v) return vector(v,0,0) end,
    Destroy=function() destroyed=destroyed+1 end,
}
local asset = {CreateEditableMeshAsync=function(_,content)
    reads=reads+1
    if content=='bad' then error('no permission') end
    coroutine.yield('reading')
    return editable
end}
local registry = {schemaVersion=2,entries={}}
local resolver={TransformedBoneFrame=function(bone) return bone.CFrame end}
local studio = true
local services = {AssetService=asset, HttpService={JSONEncode=function(_,v) local s=encode(v); encodedValues[s]=v; return s end, JSONDecode=function(_,s) return assert(encodedValues[s]) end},
    RunService={IsStudio=function() return studio end},Workspace={GetAttribute=function() return false end},
    ReplicatedStorage={Game1Shared={combat={SkeletonHeadResolver=resolver}}}}
game={GetService=function(_,name) return assert(services[name],name) end}
script={Parent={WaitForChild=function(_,name) assert(name=='HitboxAssetRegistry'); return registry end}}
require=function(x) return x end
task={wait=function() coroutine.yield('waiting') end}
local geometry=assert(loadfile(geometryPath))()
local mesh={MeshId='rbxassetid://123',MeshContent='ok'}
local a,b
local c1=coroutine.create(function() a=geometry.Read(mesh) end)
local c2=coroutine.create(function() b=geometry.Read(mesh) end)
assert(coroutine.resume(c1)); assert(coroutine.resume(c2)); assert(reads==1)
assert(coroutine.resume(c1)); assert(a.state=='ready' and a.vertexCount==2 and a.vertices[1].influences[1].weight==1)
geometry.Release(a); assert(a.vertices~=nil)
assert(coroutine.resume(c2)); assert(a==b); geometry.Release(b)
assert(b.vertices==nil and destroyed==1)
local c3=coroutine.create(function() local next=geometry.Read(mesh); assert(next~=a); geometry.Release(next) end)
assert(coroutine.resume(c3)); assert(coroutine.resume(c3)); assert(reads==2 and destroyed==2)
local bad={MeshId='rbxassetid://999',MeshContent='bad'}
local fail=geometry.Read(bad); assert(fail.state=='failed'); geometry.Release(fail)
local again=geometry.Read(bad); assert(again==fail and reads==3); geometry.Release(again)
local retry=geometry.Read(bad,true); assert(retry~=fail and retry.state=='failed' and reads==4); geometry.Release(retry)
local defs=assert(loadfile(definitionPath))()
local vis={Name='Visual'}
mesh.Name='Mesh';mesh.Parent=vis;mesh.CFrame=cf(vector(1,2,3))
local head={Name='head',Parent=mesh,CFrame=cf(vector(1,3,3)),IsA=function(_,t) return t=='Bone' end}
mesh.IsA=function(_,t) return t=='MeshPart' end
vis.GetDescendants=function() return {mesh,head} end
local binding={root={CFrame=cf(vector(1,1,1)),Position=vector(1,1,1)},visual=vis,headBone=head,headParentBone=head,
    records={{meshPart=mesh,path='Mesh',geometryKey=mesh.MeshId,scale=vector(1,1,1),bonesByName={head=head}}},bonesByName={head=head}}
assert(defs.CaptureSignature(binding)==nil)
defs.SetCaptureEnabled(true)
local signature=assert(defs.CaptureSignature(binding))
local source={broadRadius=4,sourceVertexCount=2,bodyBoxes={{kind='bone',boneName='head',recordIndex=1,localCFrame=cf(vector(0,1,0)),size=vector(1,2,3)}},headBox={kind='head',boneName='head',localCFrame=cf(vector(0,0,0)),size=vector(1,1,1)}}
defs.Record('key',signature,source); defs.Record('key',signature,source)
registry=defs.ExportCaptured();assert(#registry.entries==1)
local loaded=assert(loadfile(definitionPath))()
local decoded=assert(loaded.Lookup(binding,'key')); assert(decoded.broadRadius==4 and decoded.bodyBoxes[1].size.Y==2 and decoded.headBox.size.Z==1)
-- Translation invariant, but pose/mesh/scale changes cannot hit.
binding.root.Position=vector(10,10,10); binding.root.CFrame=cf(binding.root.Position); mesh.CFrame=cf(vector(10,11,12)); head.CFrame=cf(vector(10,12,12))
assert(loaded.Lookup(binding,'key'))
-- A world yaw around the same center does not affect the exact local bounds.
-- Rotate all geometry by 90 degrees while the root stays world-axis aligned.
mesh.CFrame=cf(vector(12,11,10),math.pi/2); head.CFrame=cf(vector(12,12,10),math.pi/2)
assert(loaded.Lookup(binding,'key'))
binding.root.Position=vector(12,10,10); binding.root.CFrame=cf(binding.root.Position)
local displaced=assert(loaded.Lookup(binding,'key')); assert(displaced.broadRadius>6 and displaced.bodyBoxes[1].size.Y==2) -- broad phase only
binding.root.Position=vector(10,10,10); binding.root.CFrame=cf(binding.root.Position)
mesh.CFrame=cf(vector(10,11,12)); head.CFrame=cf(vector(10,12,12))
head.CFrame=cf(vector(10,12.0001,12)); assert(loaded.Lookup(binding,'key')) -- one quantization unit
head.CFrame=cf(vector(10,13,12)); assert(not loaded.Lookup(binding,'key'))
head.CFrame=cf(vector(10,12,12)); binding.records[1].geometryKey='rbxassetid://456'; assert(not loaded.Lookup(binding,'key'))
binding.records[1].geometryKey=mesh.MeshId; binding.records[1].scale=vector(2,1,1); assert(not loaded.Lookup(binding,'key'))
binding.records[1].scale=vector(1,1,1); registry.entries[1].definition.bodyBoxes[1].size={0,2,3}
assert(not loaded.Lookup(binding,'key'))
registry.entries[1].definition.bodyBoxes[1].size={1,2,3}; registry.entries[2]=registry.entries[1]
local duplicate=assert(loadfile(definitionPath))(); assert(not duplicate.Lookup(binding,'key'))
head.CFrame=cf(vector(10,12.0001,12)); assert(not duplicate.Lookup(binding,'key'))
head.CFrame=cf(vector(10,12,12))
-- Session uses the same signature contract, never root dimensions.
local session=assert(loadfile(definitionPath))()
local sig=session.Signature(binding); session.Remember('session',sig,source)
assert(session.SessionLookup(binding,'session',session.Signature(binding)))
binding.root.Size=vector(9,8,7); assert(session.SessionLookup(binding,'session',session.Signature(binding)))
for i=1,360 do
    local yaw=i*math.pi/180
    local c,s=math.cos(yaw),math.sin(yaw)
    local base=vector(400+i,-53,-315)
    mesh.CFrame=cf(base,yaw); head.CFrame=cf(vector(base.X,base.Y+1,base.Z),yaw)
    local relative=vector(-1,-1,-2)
    binding.root.Position=vector(base.X+c*relative.X+s*relative.Z,base.Y+relative.Y,base.Z-s*relative.X+c*relative.Z)
    binding.root.CFrame=cf(binding.root.Position)
    binding.root.Size=vector(i,4,361-i)
    assert(session.SessionLookup(binding,'session',session.Signature(binding)), i)
end
head.CFrame=cf(vector(10,14,12)); assert(not session.SessionLookup(binding,'session',session.Signature(binding)))
studio=false; assert(not pcall(loaded.SetCaptureEnabled,true)); assert(not pcall(loaded.ExportCaptured))
print('M649: concurrent vertex leases, failure retention, capture/lookup, invalidation and Studio boundary passed')
