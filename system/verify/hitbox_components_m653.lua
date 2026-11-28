-- Exercise the production oracle and component decoder through plain Lua doubles.
local builderPath, definitionsPath, componentsPath = arg[1],arg[2],arg[3]
table.freeze=function(t)return t end
table.clone=function(t)local out={} for k,v in pairs(t) do out[k]=v end return out end
math.round=function(x)return math.floor(x+0.5) end
local V={}
local function vector(x,y,z)return setmetatable({X=x,Y=y,Z=z},V) end
V.__index=function(v,k)if k=='Magnitude' then return math.sqrt(v.X^2+v.Y^2+v.Z^2)end end
V.__add=function(a,b)return vector(a.X+b.X,a.Y+b.Y,a.Z+b.Z)end
V.__sub=function(a,b)return vector(a.X-b.X,a.Y-b.Y,a.Z-b.Z)end
V.__mul=function(a,b)return vector(a.X*b,a.Y*b,a.Z*b)end
Vector3={new=vector,zero=vector(0,0,0),one=vector(1,1,1)}
local F={}
local function cf(v)return setmetatable({Position=v,UpVector=vector(0,1,0)},F)end
F.__index=function(f,k)if k=='Rotation' then return cf(Vector3.zero) else return F[k]end end
F.__mul=function(a,b)return cf(a.Position+b.Position)end
function F:GetComponents() return self.Position.X,self.Position.Y,self.Position.Z,1,0,0,0,1,0,0,0,1 end
function F:PointToObjectSpace(p)return p-self.Position end
function F:PointToWorldSpace(p)return p+self.Position end
function F:VectorToObjectSpace(p)return p end
function F:ToObjectSpace(other)return cf(other.Position-self.Position)end
CFrame={new=cf,identity=cf(Vector3.zero)}
local encoded={}
local function serialize(v)
    if type(v)=='table' then local out={} for k,x in pairs(v) do out[#out+1]=tostring(k)..':'..serialize(x) end table.sort(out);return '{'..table.concat(out,',')..'}' end
    return tostring(v)
end
local http={JSONEncode=function(_,v)local s=serialize(v);encoded[s]=v;return s end, JSONDecode=function(_,s)return assert(encoded[s])end}
local registry={schemaVersion=2,entries={}}
local resolver={TransformedBoneFrame=function(b)return b.CFrame end}
local objects={HitboxAssetRegistry=registry,SkeletonHeadResolver=resolver}
local node={WaitForChild=function(_,name)return objects[name] or node end}
-- Lua 5.3 local initializer cannot refer to itself; set method explicitly.
node.WaitForChild=function(_,name)return objects[name] or node end
local services={ReplicatedStorage=setmetatable({Game1Shared={combat={SkeletonHeadResolver=resolver}}},{__index=node}),HttpService=http,
 RunService={IsStudio=function()return true end}, Workspace={GetAttribute=function()return false end}}
game={GetService=function(_,key)return assert(services[key])end}
script={Parent=node};require=function(x)return x end;warn=function()end
local Builder=assert(loadfile(builderPath))();objects.HitboxDefinitionBuilder=Builder
local Definitions=assert(loadfile(definitionsPath))();objects.HitboxAssetDefinitions=Definitions
local Components=assert(loadfile(componentsPath))()
local vis={Name='Visual'};local all={};vis.GetDescendants=function()return all end
local function part(name,id,x)
 local m={Name=name,Parent=vis,CFrame=cf(vector(x,0,0)),IsA=function(_,n)return n=='MeshPart'end}
 all[#all+1]=m
 return {meshPart=m,path=name,geometryKey='rbxassetid://'..id,scale=Vector3.one,bonesByName={},geometry={vertices={}}}
end
local function bone(name,parent,x,y)
 local b={Name=name,Parent=parent,CFrame=cf(vector(x,y,0)),IsA=function(_,n)return n=='Bone'end};all[#all+1]=b;return b
end
local base=part('carrier','101',0)
local neck=bone('neck',base.meshPart,0,1)
local head=bone('head',neck,0,2)
local unrelated=bone('unrelated',base.meshPart,0,4)
base.bonesByName={neck=neck,head=head,unrelated=unrelated}
local global={neck=neck,head=head,unrelated=unrelated}
local function vertex(x,y,z,weighted)
 return {position=vector(x,y,z),influences=weighted and {{boneName='neck',bindCFrame=cf(vector(0,1,0)),weight=1}} or {}}
end
local records={base}
base.geometry.vertices={vertex(0,0,0,true),vertex(0,2,0,true)}
for i=2,12 do
 local r=part('part'..i,tostring(100+i),i/10)
 r.geometry.vertices={vertex(0,0,0,i%2==0),vertex(.02,1.8,.02,false)};records[i]=r
end
local binding={entity={GetAttribute=function(_,n)if n=='CharacterArchetype' then return 'human_male'end end},visual=vis,
 records=records,bonesByName=global,headBone=head,headParentBone=neck,root={Position=Vector3.zero,CFrame=cf(Vector3.zero)}}
local oracle=assert(Builder.BuildUncached(binding))
local rows=Components.Capture(binding,oracle);assert(#rows==12)
registry.entries=rows
objects.HitboxAssetDefinitions=assert(loadfile(definitionsPath))();Components=assert(loadfile(componentsPath))()
local merged=assert(Components.Lookup(binding));assert(#merged.bodyBoxes==#oracle.bodyBoxes and merged.sourceVertexCount==oracle.sourceVertexCount)
for i,box in ipairs(merged.bodyBoxes)do assert(box.recordIndex==oracle.bodyBoxes[i].recordIndex and box.kind==oracle.bodyBoxes[i].kind)end
assert((merged.headBox.size-oracle.headBox.size).Magnitude<1e-8)
-- unrelated pose change must not invalidate a rigid component or a component
-- dependent only on neck/head. A genuinely used dependency must invalidate.
local single=Definitions.ComponentBinding(binding,2);local key='component|'..Builder.AssetKey(single)
local current=objects.HitboxAssetDefinitions
unrelated.CFrame=cf(vector(0,40,0));assert(current.LookupComponent(single,key))
neck.CFrame=cf(vector(0,1.2,0));assert(not current.LookupComponent(single,key));assert(not Components.Lookup(binding))
neck.CFrame=cf(vector(0,1,0));assert(Components.Lookup(binding))
-- Same component may be re-used at a different assembly record index.
local replacement=records[2];table.remove(records,2);table.insert(records,replacement)
assert(Components.Lookup(binding))
replacement.geometryKey='rbxassetid://999';assert(not Components.Lookup(binding))
print('M653: production component oracle union, 12-record order, pose dependency, reindex and atomic misses passed')
