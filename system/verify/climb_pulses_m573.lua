-- Execute the physical jump controller with mocked impulses and grounded state.
-- No engine simulation: verifies takeoff vector, grounded gating and lifecycle.
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
table.freeze=function(t) return t end
local shared={WaitForChild=function(self,n) if n=='Game1Shared' or n=='character' then return self end return n end}
game={GetService=function(_,n) assert(n=='ReplicatedStorage');return shared end}
Enum={Material={Air='Air',Ground='Ground'},HumanoidStateType={Freefall='Freefall'}}
local trace={Event=function() end}
local modules={CharacterConfig={JumpVelocity=34,JumpGroundIgnoreTime=.18},GameOptions={PlayerJumpSettings=function() return {heightMultiplier=2} end},MonsterNavigationTrace=trace,
    MonsterRecoveryGeometry={Horizontal=function(a) return v(a.X,0,a.Z) end}}
script={Parent={WaitForChild=function(_,name) return name end}}
require=function(name) return assert(modules[name],name) end
local C=assert(loadfile(arg[1]))()
local impulses=0
local root={Position=v(0,1,0),Parent=true,Anchored=false,AssemblyMass=2,AssemblyLinearVelocity=v(3,-2,4)}
function root:ApplyImpulse(impulse) impulses=impulses+1; self.AssemblyLinearVelocity=self.AssemblyLinearVelocity+impulse/self.AssemblyMass end
local humanoid={FloorMaterial='Ground',MoveTo=function() end,Move=function(self,d) self.direction=d end,ChangeState=function(self,s) assert(s=='Freefall');self.FloorMaterial='Air' end}
local life='Alive'
local agent={root=root,humanoid=humanoid,model={GetAttribute=function() return life end}}
local state={}
local landing=v(0,3,3)
assert(C.Begin(agent,state,landing,3,{},0,13))
assert(not root.Anchored and impulses==1 and humanoid.WalkSpeed==13)
assert(math.abs(root.AssemblyLinearVelocity.Y-34*math.sqrt(2))<1e-8)
assert(root.AssemblyLinearVelocity.X==0 and root.AssemblyLinearVelocity.Z==13)
assert(root.Position.Y==1,'no teleport or levitation')
assert(not C.Begin(agent,state,landing,3,{},0,13),'no duplicate jump')
-- A stale floor sensor in the first tick and an airborne slowdown cannot add impulses.
humanoid.FloorMaterial='Ground'
assert(C.Step(agent,state,6,{},.1)=='Moving')
humanoid.FloorMaterial='Air'
root.AssemblyLinearVelocity=v(0,-10,6)
assert(C.Step(agent,state,6,{},.5)=='Moving' and humanoid.WalkSpeed==6 and impulses==1)
humanoid.FloorMaterial='Ground'
assert(C.Step(agent,state,6,{},.7)=='Done' and state.climb==nil)
assert(not root.Anchored and root.AssemblyLinearVelocity.Y==-10)
-- If already falling, wait for ground instead of jumping again in midair.
humanoid.FloorMaterial='Air'
assert(C.Begin(agent,state,landing,3,{},1,6) and impulses==1)
assert(C.Step(agent,state,6,{},1.2)=='Moving' and impulses==1)
humanoid.FloorMaterial='Ground'
assert(C.Step(agent,state,6,{},1.3)=='Moving' and impulses==2)
local before=root.AssemblyLinearVelocity
C.Stop(state); assert(state.climb==nil and root.AssemblyLinearVelocity==before and humanoid.direction.Magnitude==0)
-- Death owns the root; cleanup never changes anchoring or momentum.
humanoid.FloorMaterial='Air';assert(C.Begin(agent,state,landing,3,{},2,6))
root.Anchored=true;life='Dying';C.Stop(state);assert(root.Anchored and state.climb==nil)
print('Ballistic jump: character height, forward velocity, ground gating, cleanup passed')
