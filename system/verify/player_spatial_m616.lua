local Grid = dofile('src/server/actor/PlayerSpatialGrid.luau')
local function nearest(players, x, z, radius, allowed)
    local best, target = radius, nil
    for _, p in ipairs(players) do
        local d = math.sqrt((p.x-x)^2 + (p.z-z)^2)
        if d <= best and p.alive and allowed(p) then best, target = d, p end
    end
    return target
end
local function verify(players, grid, x, z, radius, allowed)
    local candidates = grid:Query(x,z,radius)
    assert(nearest(players,x,z,radius,allowed) == nearest(candidates,x,z,radius,allowed))
    local seen, last = {}, 0
    for _, p in ipairs(candidates) do
        assert(not seen[p] and p.order > last)
        seen[p], last = true, p.order
    end
    for _,p in ipairs(players) do
        if math.sqrt((p.x-x)^2+(p.z-z)^2) <= radius then assert(seen[p]) end
    end
end
math.randomseed(616)
local queries = 0
for _, population in ipairs({0,1,10,100,500}) do
    for trial=1,8 do
        local players, grid = {}, Grid.new(32)
        for i=1,population do
            local p = {order=i,x=math.random(-512,512),z=math.random(-512,512),y=math.random(-10000,10000),alive=i%7~=0,zone=i%3}
            players[i]=p; grid:Add(p,p.x,p.z)
        end
        for q=1,30 do
            local radius=({0,16,32,70,10000,math.huge})[(q-1)%6+1]
            local zone=q%3
            verify(players,grid,math.random(-512,512),math.random(-512,512),radius,function(p) return p.zone==zone end)
            queries=queries+1
        end
    end
end
-- Equal distances in different cells; last eligible player wins, irrespective of Y.
local a={order=1,x=-32,z=0,y=1000,alive=true}; local b={order=2,x=32,z=0,y=-1000,alive=true}
local g=Grid.new(32); g:Add(a,a.x,a.z); g:Add(b,b.x,b.z)
assert(nearest(g:Query(0,0,32),0,0,32,function() return true end)==b)
verify({a,b},g,0,0,32,function() return true end)
assert(#g:Query(-32,0,0)==1)
assert(#g:Query(0,0,-1)==0)
-- Exercise the actual service and root resolver with Roblox API mocks.
table.freeze=table.freeze or function(t) return t end
local Root=dofile('src/server/actor/ActorTargetRoot.luau')
local function part(x,z,y,canQuery)
    return {Position={X=x,Y=y,Z=z},CanQuery=canQuery,IsA=function(_,kind) return kind=='BasePart' end}
end
local function character(parts,primary)
    return {PrimaryPart=primary,FindFirstChild=function(_,name) return parts[name] end}
end
local p1={Character=character({RootCollider=part(-32,0,500,true),HumanoidRootPart=part(999,0,0,false)})}
local p2={Character=character({HumanoidRootPart=part(32,0,-500,false)})}
local p3={Character=character({},part(0,0,2000,false))}
local p4={Character=character({RootCollider={IsA=function() return false end},HumanoidRootPart=part(0,0,0,true)})}
local roster={p1,p2,p3,p4}; local calls=0
local function signal() return {Connect=function(self,cb) self.cb=cb end} end
local players={PlayerAdded=signal(),PlayerRemoving=signal(),GetPlayers=function() calls=calls+1; return roster end}
local env=setmetatable({game={GetService=function(_,name) assert(name=='Players'); return players end},script={Parent={WaitForChild=function(_,name)return name end}},require=function(name) return ({ActorTargetRoot=Root,PlayerSpatialGrid=Grid})[name] end},{__index=_G})
local index=assert(loadfile('src/server/actor/PlayerSpatialIndex.luau','t',env))()
local origin={X=0,Z=0,Y=0}
index.BeginBatch(); assert(calls==0)
assert(#index.Query(origin,32)==3); assert(#index.Query(origin,32)==3); assert(calls==1)
-- Scripted teleport / character replacement invalidates in the same dispatch.
p1.Character=character({RootCollider=part(1000,1000,0,true)}); index.Invalidate()
assert(#index.Query(origin,32)==2); assert(calls==2)
p2.Character=nil; index.Invalidate(); assert(#index.Query(origin,32)==1)
table.remove(roster,3); players.PlayerRemoving.cb(); assert(#index.Query(origin,32)==0)
index.EndBatch(); local before=calls; index.BeginBatch(); index.EndBatch(); assert(calls==before)
-- Outside a scheduler batch, no cached positions survive.
p1.Character=character({RootCollider=part(0,0,0,true)}); assert(#index.Query(origin,0)==1)
p1.Character=nil; assert(#index.Query(origin,0)==0)
assert(calls==before+2)
print('M616: '..queries..' randomized target-equivalence queries; tie, boundaries, root fallback, batch and invalidation OK')
