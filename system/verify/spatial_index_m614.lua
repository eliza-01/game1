-- Execute production index using a deterministic mock of the native query.
-- Mock returns centers inside the query box, a stricter subset than root AABBs.
local V={}; V.__index=V
function V.new(x,y,z) return setmetatable({X=x,Y=y,Z=z},V) end
function V.__add(a,b) return V.new(a.X+b.X,a.Y+b.Y,a.Z+b.Z) end
function V.__sub(a,b) return V.new(a.X-b.X,a.Y-b.Y,a.Z-b.Z) end
function V.__mul(a,b) return V.new(a.X*b,a.Y*b,a.Z*b) end
function V:Dot(b) return self.X*b.X+self.Y*b.Y+self.Z*b.Z end
function V:Cross(b) return V.new(self.Y*b.Z-self.Z*b.Y,self.Z*b.X-self.X*b.Z,self.X*b.Y-self.Y*b.X) end
function V:unit() return self*(1/math.sqrt(self:Dot(self))) end
V.xAxis=V.new(1,0,0); V.yAxis=V.new(0,1,0); V.zAxis=V.new(0,0,1)
Vector3=V
CFrame={}
function CFrame.new(p) return {p=p,x=V.xAxis,y=V.yAxis,z=V.zAxis} end
function CFrame.lookAt(p,target,up)
    local z=(target-p):unit(); local x=up:Cross(z):unit()
    return {p=p,x=x,y=z:Cross(x),z=z}
end
OverlapParams={new=function() return {} end}; Enum={RaycastFilterType={Include='Include'}}
local function signal()
    local s={callbacks={}}
    function s:Connect(fn)
        self.callbacks[fn]=true
        return {Disconnect=function() self.callbacks[fn]=nil end}
    end
    function s:fire() for fn in pairs(self.callbacks) do fn() end end
    return s
end
local world={calls=0}
local function coords(frame,p)
    local d=p-frame.p; return d:Dot(frame.x),d:Dot(frame.y),d:Dot(frame.z)
end
function world:GetPartBoundsInBox(frame,size,params)
    self.calls=self.calls+1
    assert(params.MaxParts==0 and params.RespectCanCollide==false and params.FilterType=='Include')
    self.lastFilter=params.FilterDescendantsInstances
    local result={}
    for _,part in ipairs(self.lastFilter) do
        local x,y,z=coords(frame,part.position)
        if math.abs(x)<=size.X/2 and math.abs(y)<=size.Y/2 and math.abs(z)<=size.Z/2 then
            result[#result+1]=part; result[#result+1]=part -- exercise dedup
        end
    end
    return result
end
local Index=dofile('src/shared/world/NativePartSpatialIndex.luau')
local index=Index.new(world); local other=Index.new(world)
local records={}
local function add(p,r)
    local owner={Destroying=signal()}; local part={position=p,CanQuery=true,Destroying=signal()}
    local record={owner=owner,part=part,r=r}; records[#records+1]=record
    index:Register(owner,part,r,record); return record
end
local function verify(results,required)
    local seen={}
    for _,r in ipairs(results) do assert(not seen[r]); seen[r]=true end
    for _,r in ipairs(records) do if required(r) then assert(seen[r],'broadphase missed reference candidate') end end
end
math.randomseed(614)
local function vec() return V.new(math.random(-100,100),math.random(-100,100),math.random(-100,100)) end
for i=1,250 do add(vec(),math.random(1,14)) end
local giant=add(V.new(35,0,0),40)
local zero=V.new(0,0,0)
for i=1,100 do
    local origin=vec(); local direction=vec():unit(); local limit=math.random(1,150); local radius=math.random(1,40)
    verify(index:QueryRadius(origin,radius),function(r)
        local d=r.part.position-origin; return d:Dot(d)<=(radius+r.r)^2
    end)
    verify(index:QueryRay(origin,direction,limit),function(r)
        local d=r.part.position-origin; local t=math.max(0,math.min(limit,d:Dot(direction)))
        local e=d-direction*t; return e:Dot(e)<=r.r^2
    end)
    local frame=CFrame.lookAt(origin,origin+direction,math.abs(direction:Dot(V.yAxis))>.99 and V.xAxis or V.yAxis)
    local size=V.new(12,22,8)
    verify(index:QueryBox(frame,size),function(r)
        local x,y,z=coords(frame,r.part.position)
        return math.max(0,math.abs(x)-6)^2+math.max(0,math.abs(y)-11)^2+math.max(0,math.abs(z)-4)^2<=r.r^2
    end)
end
verify(index:QueryRadius(zero,1),function(r) return r==giant end)
assert(#other:QueryRadius(zero,1000)==0)
local filter=world.lastFilter
index:QueryRadius(zero,1); assert(world.lastFilter==filter,'filter rebuilt without change')
giant.part.position=V.new(0,1000,0)
verify(index:QueryRay(zero,V.yAxis,1000),function(r) return r==giant end)
local function absent(results,record) for _,r in ipairs(results) do assert(r~=record) end end
giant.owner.Destroying:fire(); absent(index:QueryRadius(zero,2000),giant); assert(index.maxRadius<=14)
local r=records[1]; r.part.Destroying:fire(); absent(index:QueryRadius(zero,2000),r)
local replacement=add(zero,2); index:Remove(replacement.owner); absent(index:QueryRadius(zero,2000),replacement)
for _,record in ipairs(records) do index:Remove(record.owner) end
local calls=world.calls; assert(#index:QueryRadius(zero,100)==0 and world.calls==calls)
assert(next(index.byPart)==nil and next(index.byOwner)==nil and #index.params.FilterDescendantsInstances==0)
print('M614: 300 randomized reference queries + lifecycle/vertical/large/teleport passed')
