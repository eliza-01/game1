local mt={}
local function v(x,y,z) return setmetatable({X=x,Y=y,Z=z},mt) end
mt.__add=function(a,b) return v(a.X+b.X,a.Y+b.Y,a.Z+b.Z) end
mt.__sub=function(a,b) return v(a.X-b.X,a.Y-b.Y,a.Z-b.Z) end
mt.__mul=function(a,b) return v(a.X*b,a.Y*b,a.Z*b) end
mt.__div=function(a,b) return v(a.X/b,a.Y/b,a.Z/b) end
mt.__unm=function(a) return a*-1 end
mt.__index=function(a,k)
    if k=='Magnitude' then return math.sqrt(a.X^2+a.Y^2+a.Z^2) end
    if k=='Unit' then return a/a.Magnitude end
end
Vector3={new=v,yAxis=v(0,1,0)}
table.freeze=function(t) return t end
local B=assert(loadfile(arg[1]))()
local Speed=assert(loadfile(arg[2]))()
local s={};B.Begin(s)
local checks=0
local function noPoint() checks=checks+1;return nil end
assert(B.Step(s,v(0,0,0),v(5,0,0),10,2,100,0,noPoint)=='Retreat')
assert(B.IsRetreating(s) and checks==0 and B.WaitSeconds(s,200)==0,'rooted retreat does not start the clock')
assert(B.Step(s,v(0,0,0),v(5,0,0),10,2,200,10,noPoint)=='Wait')
assert(B.WaitSeconds(s,201)==1 and not B.IsRetreating(s))
assert(B.Step(s,v(0,0,0),v(5,0,0),10,2,202,10,noPoint)=='Wait','stationary target inside range does not loop')
assert(B.Step(s,v(0,0,0),v(11,0,0),10,2,203,10,noPoint)=='Wait')
assert(B.Step(s,v(0,0,0),v(10,0,0),10,2,204,10,noPoint)=='Reengage' and checks==1)
B.Begin(s)
local function point() return v(-6,0,0) end
assert(B.Step(s,v(0,0,0),v(5,0,0),10,2,300,10,point)=='Retreat')
assert(B.Step(s,v(0,0,0),v(5,0,0),10,2,301,10,point)=='Retreat')
assert(B.Step(s,v(0,0,0),v(5,0,0),10,2,302,10,point)=='Wait','a physically stalled retreat is bounded')
local config={blockedRetreatSpeedMultiplier=1,blockedReengageSpeedMultiplier=1.7,rescueRouteSpeedMultiplier=1.5}
assert(Speed.Multiplier(s,config)==1)
s.blockedPursuit=nil;s.reengaging=true
assert(Speed.Multiplier(s,config)==1.7)
s.mode='RescueRoute';assert(Speed.Multiplier(s,config)==1.5,'do not multiply speed factors')
s.mode='Climb';s.plan={};s.planKind='RescueRoute';assert(Speed.Multiplier(s,config)==1.5)
s.mode='Direct';s.plan=nil;s.reengaging=nil;assert(Speed.Multiplier(s,config)==1)

-- Physical-query contract: one bounded step, floor support, Terrain not ignored,
-- wall rejects straight approach, legal alternate direction can be selected.
local terrain,actor={},{}
local world={Terrain=terrain}
local clearFloor=true;local wall=false;local casts=0
function world:Raycast(origin,delta,params)
    assert(#params.FilterDescendantsInstances==1 and params.FilterDescendantsInstances[1]==actor)
    if clearFloor then return {Position=v(origin.X,0,origin.Z)} end
end
function world:Blockcast(cf,size,delta,params)
    casts=casts+1
    if wall and math.abs(delta.Z)<.01 then return {} end
end
game={GetService=function() return world end}
script={Parent={WaitForChild=function(_,name) return name end}}
require=function(name)
    assert(name=='MonsterRecoveryGeometry')
    return {Horizontal=function(p) return v(p.X,0,p.Z) end,
        Params=function() return {FilterDescendantsInstances={terrain,actor}} end,
        Body=function() return v(0,0,0) end}
end
local G=assert(loadfile(arg[3]))()
local agent={root={CFrame={},Size=v(2,2,2)}}
local root=v(0,3,0);local target=v(5,3,0)
local dest=G.FindPoint(agent,root,target,12,function() return true end)
assert(dest.X==-6 and dest.Y==3 and casts==1)
wall=true;casts=0;dest=G.FindPoint(agent,root,target,12,function() return true end)
assert(dest and math.abs(dest.Z)>1 and casts==2)
assert(G.FindPoint(agent,root,target,12,function() return false end)==nil,'respect pursuit boundary')
clearFloor=false;assert(G.FindPoint(agent,root,target,12,function() return true end)==nil,'reject unsupported step')
print('M591 blocked policy, speed and retreat geometry contracts passed')
