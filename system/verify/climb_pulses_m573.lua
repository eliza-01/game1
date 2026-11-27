-- Execute the real climb controller against deterministic mocked movement.
-- This checks control/state, not Roblox physics.
local mt={}
local function v(x,y,z) return setmetatable({X=x,Y=y,Z=z},mt) end
mt.__add=function(a,b) return v(a.X+b.X,a.Y+b.Y,a.Z+b.Z) end
mt.__sub=function(a,b) return v(a.X-b.X,a.Y-b.Y,a.Z-b.Z) end
mt.__mul=function(a,b) return v(a.X*b,a.Y*b,a.Z*b) end
mt.__div=function(a,b) return v(a.X/b,a.Y/b,a.Z/b) end
mt.__index=function(a,k)
    if k=='Magnitude' then return math.sqrt(a.X^2+a.Y^2+a.Z^2) end
    if k=='Unit' then return a/a.Magnitude end
end
Vector3={new=v,yAxis=v(0,1,0),zero=v(0,0,0)}
math.clamp=function(x,a,b) return math.max(a,math.min(x,b)) end
table.freeze=function(t) return t end
local casts=0
local ceiling=false
local wallHeight=4.5
local world={Blockcast=function(_,cf,size,delta)
    casts=casts+1
    if delta.Y>0 and ceiling then return {Distance=.05} end
    if delta.Z>0 and cf.Y<wallHeight then return {Distance=.05} end
end}
game={GetService=function() return world end}
RaycastParams={new=function() return {} end}
Enum={RaycastFilterType={Exclude='Exclude'}}
local trace={Enabled=function() return false end,Event=function() end}
local modules={MonsterNavigationConfig={climbSpeed=8},MonsterNavigationTrace=trace,
    MonsterRecoveryGeometry={Horizontal=function(a) return v(a.X,0,a.Z) end,Body=function() return v(0,0,0),4.62 end}}
script={Parent={WaitForChild=function(_,name) return name end}}
require=function(name) return assert(modules[name],name) end
local C=assert(loadfile(arg[1]))()
local root=setmetatable({pos=v(0,1,0),Size=v(2,2,1),Parent=true,Anchored=false,CollisionGroup='NPC',SetNetworkOwner=function(self,owner) self.networkReset=true end},{
    __index=function(t,k) if k=='Position' or k=='CFrame' then return t.pos end end,
    __newindex=function(t,k,val) if k=='CFrame' then t.pos=val else rawset(t,k,val) end end})
local stops=0
local humanoid={Move=function(_,d) assert(d.Magnitude==0) end,MoveTo=function() stops=stops+1 end}
local life='Alive'
local agent={root=root,humanoid=humanoid,model={GetAttribute=function() return life end}}
local state={}
local landing=v(0,3,3)
assert(C.Begin(agent,state,landing,3,{},0))
assert(root.Anchored and casts==0 and stops==1)
assert(not C.Begin(agent,state,landing,3,{},0),'no duplicate climb')
local c=state.climb
local lastY=root.Position.Y
for i=1,12 do
    local r=C.Step(agent,state,10,{},i*.1)
    assert(root.Position.Y>=lastY,'no gravity slide while climbing')
    lastY=root.Position.Y
    if r=='Done' then break end
end
assert(root.Position.Y>=wallHeight and root.Position.Y<=c.maxY)
assert(root.Position.Z>=2.55,'crossed lip using bounded displacement')
assert(state.climb==nil and not root.Anchored and root.networkReset,'release physical movement')
-- Low ceilings prevent displacement; timeout is based on new progress.
root.pos=v(0,1,0);ceiling=true
assert(C.Begin(agent,state,landing,3,{},20))
for i=1,69 do assert(C.Step(agent,state,10,{},20+i*.1)=='Moving') end
assert(root.Position.Y==1)
assert(C.Step(agent,state,10,{},27.1)=='Failed')
C.Stop(state); assert(not root.Anchored and state.climb==nil)
-- A high obstruction never becomes infinite levitation.
root.pos=v(0,1,0);ceiling=false;wallHeight=100
assert(C.Begin(agent,state,landing,3,{},30));c=state.climb
for i=1,20 do assert(C.Step(agent,state,10,{},30+i*.1)=='Moving') end
assert(root.Position.Y<=c.maxY+1e-6 and root.Position.Z==0)
-- Death owns anchoring after cleanup.
life='Dying'; C.Stop(state); assert(root.Anchored and state.climb==nil)
print('Kinematic climb: lift, lip, bounded height, ceiling, cleanup passed')
