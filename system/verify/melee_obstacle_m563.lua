-- Execute the production geometry functions with deterministic mocked queries.
local mt={}
local function v(x,y,z) return setmetatable({X=x,Y=y,Z=z},mt) end
mt.__add=function(a,b) return v(a.X+b.X,a.Y+b.Y,a.Z+b.Z) end
mt.__sub=function(a,b) return v(a.X-b.X,a.Y-b.Y,a.Z-b.Z) end
mt.__mul=function(a,b) return v(a.X*b,a.Y*b,a.Z*b) end
mt.__unm=function(a) return v(-a.X,-a.Y,-a.Z) end
mt.__index=function(a,k) if k=='Magnitude' then return math.sqrt(a.X^2+a.Y^2+a.Z^2) end end
Vector3={new=v,yAxis=v(0,1,0)}
CFrame={lookAt=function(origin,target) return {Position=origin} end}
local mode='fence'
local world={Terrain={}}
local rayCalls,blockCalls=0,0
function world:FindFirstChild() return nil end
function world:Raycast(origin,delta,params)
    assert(params.RespectCanCollide and params.FilterDescendantsInstances[2]==self.Terrain)
    rayCalls=rayCalls+1
    if delta.Y<0 then
        -- Thin 0.3-stud fence: intended landing centre is beyond the top.
        if origin.X>=1.5 and origin.X<1.8 then return {Position=v(origin.X,1.5,0),Normal=v(0,1,0)} end
        return nil
    end
    assert(delta.Y==0,'melee check must not aim over the fence at an elevated target')
    if mode=='fence' then return {Position=v(1.5,origin.Y,0),Distance=1.5} end
    return nil
end
function world:Blockcast(cf,size,delta,params)
    blockCalls=blockCalls+1
    assert(delta.Y==0)
    if mode=='body' then return {} end

end
game={GetService=function(_,name) if name=='Workspace' then return world end return {GetPlayers=function() return {} end} end}
script={Parent={WaitForChild=function() return {} end}}
local trace={Bind=function() end,Ray=function() end}
script.Parent.WaitForChild=function(_,name) return name end
require=function(name) return name=="MonsterNavigationTrace" and trace or {} end
Enum={RaycastFilterType={Exclude='Exclude'}}
RaycastParams={new=function() return {} end}; OverlapParams={new=function() return {} end}
table.freeze=function(x) return x end
local G=assert(loadfile(arg[1]))()
local agent={root={Position=v(0,2.8,0),Size=v(2,2,1),CFrame={},CollisionGroup='Game1ActorBodies'},humanoid={HipHeight=1.8},model={FindFirstChild=function() return nil end}}
assert(not G.MeleeClear(agent,v(4,5,0)),'elevated target behind fence')
assert(blockCalls==0,'early exit on foot ray')
mode='body'; assert(not G.MeleeClear(agent,v(4,5,0)),'body obstruction even when foot ray misses')
mode='clear'; assert(G.MeleeClear(agent,v(4,5,0)),'open path')
local params=G.Params(agent)
local lower={Distance=1.5,Position=v(1.5,.25,0)}
local landing,rise=G.ClimbPoint(agent,v(0,0,0),3.8,1,v(1,0,0),nil,lower,params)
assert(landing and math.abs(landing.X-2.75)<1e-6 and rise==1.5,'thin fence contact top')
assert(not G.ClimbPoint(agent,v(0,0,0),3.8,1,v(1,0,0),{Distance=1.5},lower,params),'high wall')
assert(not G.ClimbPoint(agent,v(0,0,0),3.8,1,v(1,0,0),nil,{Distance=5,Position=v(5,.25,0)},params),'too distant')
-- M566: no fallback sweeps. The authored world has no narrow joints.
mode='clear'
local before=blockCalls
local p,h,probe=G.ProbeClimb(agent,v(0,0,0),3.8,1,v(1,0,0),5,params)
assert(not p and not h and probe=='Ray' and blockCalls==before,'no width sweep on a ray miss')
-- The direct gate is horizontal, at head height, limited to the attack reach.
mt.__div=function(a,b) return v(a.X/b,a.Y/b,a.Z/b) end
local prior=mt.__index
mt.__index=function(a,k) if k=='Unit' then return a/a.Magnitude end return prior(a,k) end
local original=world.Raycast
local origin,delta
world.Raycast=function(_,a,d) origin,delta=a,d; return {Distance=2} end
assert(G.HeadObstacle(v(0,0,0),4,v(12,9,0),3,params))
assert(origin.Y==3.95 and delta.Y==0 and delta.X==3,'primary ray stays horizontal and within attack reach')
G.HeadObstacle(v(0,0,0),4,v(1,9,0),3,params)
assert(delta.X==1,'do not detect obstacles behind the target')
local head={Distance=1.5}
local casts=0
world.Raycast=function(_,a,d) casts=casts+1; assert(a.Y==.25); return {Distance=1.5,Position=v(1.5,.25,0)} end
assert(not G.ProbeClimb(agent,v(0,0,0),3.8,1,v(1,0,0),3,params,head))
assert(casts==1,'reuse confirmed head hit, only foot ray needed for wall')
world.Raycast=original
print('M563 fence and M566 primary rays passed')
