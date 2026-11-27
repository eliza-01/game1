local mt={}
local function v(x,y,z) return setmetatable({X=x,Y=y,Z=z},mt) end
mt.__add=function(a,b) return v(a.X+b.X,a.Y+b.Y,a.Z+b.Z) end
mt.__sub=function(a,b) return v(a.X-b.X,a.Y-b.Y,a.Z-b.Z) end
mt.__index=function(a,k) if k=='Magnitude' then return math.sqrt(a.X^2+a.Y^2+a.Z^2) end end
Vector3={new=v}; table.freeze=function(t) return t end
local B=assert(loadfile(arg[1]))()
local s={}; local origin=v(0,0,0); local calls=0
local function noPoint() calls=calls+1; return nil end
local function step(target,now) return B.Step(s,origin,target,40,2,now,13,noPoint) end
B.Begin(s); assert(step(v(5,8,0),0)=='Wait')
assert(B.IsWaiting(s)); assert(step(v(5,8,0),1)=='Wait')
assert(step(v(5,7.9,0),2)=='Wait','jitter does not trigger search')
local a,_,why=step(v(5,4,0),3); assert(a=='Reengage' and why=='TargetApproached','descending within range wakes')
assert(step(v(5,4,0),4)=='Wait' and calls==1,'one wake, no repeated search')
B.NotifyDamage(s); a,_,why=step(v(5,4,0),5); assert(a=='Reengage' and why=='Damage')
assert(step(v(5,4,0),6)=='Wait' and calls==1)
B.Begin(s); assert(step(v(42,0,0),7)=='Wait'); assert(step(v(41,0,0),8)=='Wait')
a,_,why=step(v(40,0,0),9); assert(a=='Reengage' and why=='RangeEntered')
B.Begin(s); B.NotifyDamage(s); assert(step(v(5,0,0),10)=='Wait'); assert(step(v(5,0,0),11)=='Wait','retreat damage does not queue wait wake')
local obstacle,melee,allowed=false,true,true
local world={Raycast=function() if obstacle then return {Instance={IsDescendantOf=function() return false end}} end end}
game={GetService=function(_,name) if name=='Workspace' then return world end return {} end}
local node={}; node.Parent=node; node.WaitForChild=function(_,name) if name=='dev' then return node end return name end
script={Parent=node}; Enum={RaycastFilterType={Exclude='Exclude'}}; RaycastParams={new=function() return {} end}
require=function(name)
    if name=='MonsterBlockedPursuit' then return B end
    if name=='MonsterRecoveryGeometry' then return {MeleeClear=function() return melee end} end
    if name=='MonsterDeathChasePolicy' then return {AllowsPosition=function() return allowed end} end
    if name=='GameplayTestIsolation' then return {Allows=function() return true end} end
    error(name)
end
local policy=assert(loadfile(arg[2]))()
local attrs={MonsterAttackRadius=3,MonsterCombatType='melee',Damageable=true,LifeState='Alive'}
local function getAttr(_,k) return attrs[k] end
local root={Position=v(2,0,0),IsA=function() return true end}
local target={Parent={},GetAttribute=getAttr,FindFirstChild=function() return root end}
local agent={model={GetAttribute=getAttr},root={Position=origin},recoveryNavigation=s}
assert(policy.IsRecovering(agent)); assert(policy.CanBeginTargetedCast(agent,target),'waiting never suppresses reachable melee attack')
obstacle=true; assert(not policy.CanBeginTargetedCast(agent,target)); obstacle=false
melee=false; assert(not policy.CanBeginTargetedCast(agent,target)); melee=true
root.Position=v(2,6,0); assert(not policy.CanBeginTargetedCast(agent,target),'vertical reach unchanged')
root.Position=v(4,0,0); assert(not policy.CanBeginTargetedCast(agent,target),'range unchanged')
root.Position=v(2,0,0); allowed=false; assert(not policy.CanBeginTargetedCast(agent,target)); allowed=true
attrs.LifeState='Dead'; assert(not policy.CanBeginTargetedCast(agent,target)); attrs.LifeState='Alive'
for _,state in ipairs({{plan={}},{climb={}},{mode='Retry'},{blockedPursuit={phase='Retreat'}}}) do
    agent.recoveryNavigation=state; assert(not policy.CanBeginTargetedCast(agent,target),'active recovery owns movement')
end
agent.recoveryNavigation=nil; assert(policy.CanBeginTargetedCast(agent,target))
print('M594 wait/attack regression passed')
