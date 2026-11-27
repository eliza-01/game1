-- Execute real Detour with an analytic axis-aligned wall and swept footprint.
local mt={}
local function v(x,y,z) return setmetatable({X=x,Y=y,Z=z},mt) end
mt.__add=function(a,b) return v(a.X+b.X,a.Y+b.Y,a.Z+b.Z) end
mt.__sub=function(a,b) return v(a.X-b.X,a.Y-b.Y,a.Z-b.Z) end
mt.__mul=function(a,b) return v(a.X*b,a.Y*b,a.Z*b) end
mt.__div=function(a,b) return v(a.X/b,a.Y/b,a.Z/b) end
mt.__index=function(a,k)
    if k=='Magnitude' then return math.sqrt(a.X^2+a.Y^2+a.Z^2) end
    if k=='Unit' then return a/a.Magnitude end
    if k=='Dot' then return function(a,b) return a.X*b.X+a.Y*b.Y+a.Z*b.Z end end
end
Vector3={new=v,yAxis=v(0,1,0)}
CFrame={new=function(origin) return {Position=origin} end,lookAt=function(origin) return {Position=origin} end}
local wall={Size=v(8,12,4),CFrame={PointToWorldSpace=function(_,p) return p end}}
local world={}
local function blocked(a,d,marginX,marginZ)
    local t0,t1=0,1
    for _,axis in ipairs({'X','Z'}) do
        local half=axis=='X' and 4+marginX or 2+marginZ
        if math.abs(d[axis])<1e-8 then
            if math.abs(a[axis])>half then return false end
        else
            local u,w=(-half-a[axis])/d[axis],(half-a[axis])/d[axis]
            t0=math.max(t0,math.min(u,w));t1=math.min(t1,math.max(u,w))
            if t0>t1 then return false end
        end
    end
    return true
end
function world:Raycast(a,d) if blocked(a,d,0,0) then return {} end end
function world:Blockcast(cf,size,d) if blocked(cf.Position,d,size.X/2,size.Z/2) then return {} end end
function world:GetPartBoundsInBox(_,size)
    assert(size.Y==.2,'only head-level slab')
    return {wall}
end
game={GetService=function() return world end}
script={Parent={WaitForChild=function() return 'config' end}}
package.loaded.config={searchDistance=40,searchWidth=60}
local trace={Enabled=function() return false end,Event=function() end,Ray=function() end,Bind=function() end,V=function() return "mock" end,Changed=function() end,Rate=function() end,RouteObserver=function() return nil end}
script.Parent.WaitForChild=function(_,name) return name=="MonsterNavigationTrace" and "trace" or "config" end
package.loaded.trace=trace
table.freeze=function(t) return t end
local G=assert(loadfile(arg[1]))()
local start,goal=v(0,0,-3.05),v(0,0,8)
local plan=G.Detour({},start,goal,4,1,{}, {},function() return true end)
assert(plan and #plan.points==2,'opposite faces require two corners even at contact')
assert(plan.points[1].Z<start.Z,'padded near corner can be behind the actor at contact')
local a=start;local cost=0
for _,p in ipairs(plan.points) do
    assert(not blocked(a,p-a,1,1),'each leg clears entire swept width')
    cost=cost+(p-a).Magnitude;a=p
end
assert(not blocked(a,goal-a,1,1),'exit clears body width')
assert(math.abs(plan.cost-cost-(goal-a).Magnitude)<1e-6,'full path length')
assert(G.Detour({},start,goal,4,1,{}, {},function(p) return p.Z<0 end)==nil,'no valid exit => no plan')
local one=G.Detour({},start,v(8,0,0),4,1,{}, {},function() return true end)
assert(one and #one.points==1,'single corner still chosen when sufficient')
print('M564 two-corner obstacle detour passed')

-- M574: a raised target is visible above a wall beyond the short 10-stud
-- attack lookahead. Only the full horizontal exit ray detects that wall.
local realRay=world.Raycast
local castCount=0
function world:Raycast(a,d)
    castCount=castCount+1
    if math.abs(d.Z)<1e-8 then return nil end
    local u=(20-a.Z)/d.Z
    if u>=0 and u<=1 and a.Y+d.Y*u<=6 and a.Y+d.Y*u>=0 then return {Distance=d.Magnitude*u} end
end
local raised=v(0,12,50)
assert(G.HeadClear(v(0,0,0),4,raised+Vector3.yAxis*.1,{}))
assert(G.HeadObstacle(v(0,0,0),4,raised,10,{})==nil)
castCount=0
assert(not G.RecoveryExitClear(v(0,0,0),4,raised,{}),'wall at 20 vetoes visible heels at 50')
assert(castCount==2,'no extra casts in exit gate')
-- M585: report exact hit and short-circuit without an extra cast.
local hit={Instance=wall}
for _,blockedAt in ipairs({1,2,0}) do
    castCount=0
    function world:Raycast(a,d)
        castCount=castCount+1
        if castCount==blockedAt then return hit end
    end
    local ok,reason,result=G.HeadPassageClear(v(0,0,0),v(0,0,10),4,{})
    assert(castCount==1)
    assert(ok==(blockedAt~=1))
    if blockedAt==1 then assert(result==hit and reason=='HeadBlocked') end
    castCount=0
    ok,reason,result=G.RecoveryExitClear(v(0,0,0),4,v(0,0,10),{})
    assert(castCount==(blockedAt==1 and 1 or 2))
    assert(ok==(blockedAt==0))
    if blockedAt~=0 then assert(result==hit and reason==(blockedAt==1 and 'HeelBlocked' or 'HeadBlocked')) end
end
-- Local collision detour retains its head-level passage test.
castCount=0
function world:Raycast(a,d)
    castCount=castCount+1
    assert(math.abs(a.Y-5.95)<1e-6 and a.X==1 and a.Z==3)
    assert(d.X==7 and d.Y==3 and d.Z==9)
end
assert(G.HeadPassageClear(v(1,2,3),v(8,5,12),4,{}))
assert(castCount==1)
-- M587: route entry casts exactly from feet to the candidate, once.
local foot,point=v(1,2,3),v(8,5,12)
local entryParams={}
for _,blocked in ipairs({false,true}) do
    castCount=0
    function world:Raycast(a,d,params)
        castCount=castCount+1
        assert(a.X==1 and a.Y==2 and a.Z==3,'origin must be feet')
        assert(d.X==7 and d.Y==3 and d.Z==9,'end must be route point')
        assert(params==entryParams,'reuse collision filters')
        if blocked then return hit end
    end
    local ok,reason,result=G.RouteEntryClear(foot,point,entryParams)
    assert(castCount==1 and ok==not blocked)
    if blocked then assert(reason=='FootBlocked' and result==hit) end
    assert(G.RouteEntryClear(foot,foot,entryParams) and castCount==1)
end
world.Raycast=realRay
print('M587 foot-only route entry passed')
print('M574 full-length recovery exit rejects far high wall')

-- Execute the actual navigation state machine, with time and a stationary actor.
-- Geometry and movement are mocked; never claim this is a Studio physics test.
local t=0; os.clock=function() return t end
math.clamp=function(x,a,b) return math.max(a,math.min(x,b)) end
math.round=function(x) return math.floor(x+.5) end
Vector3.zero=v(0,0,0)
local attrs,commands={},{}
local root={Position=v(0,0,0),Parent=true}
local model={Parent=true,GetAttribute=function(_,k) return attrs[k] end,SetAttribute=function(_,k,x) attrs[k]=x end}
local agent={active=true,returning=true,root=root,model=model,humanoid={Move=function() end,MoveTo=function(_,p) commands[#commands+1]=p end}}
local isClear=false
local high=false
local wallDistance=2
local lastHeadReach=0
local headCalls,heelCalls=0,0
local expectedHeelY=.1
local searches=0
local geom={Horizontal=G.Horizontal,Body=function() return root.Position,4,1 end,Params=function() return {} end,Overlap=function() return {} end,
    ProbeClimb=function() return nil,nil,'Ray',high and {Distance=wallDistance} or nil end,RouteEntryClear=function() return isClear end,HeadClear=function(_,_,goal) heelCalls=heelCalls+1; assert(math.abs(goal.Y-expectedHeelY)<1e-6); return isClear end,
    HeadObstacle=function(_,_,_,reach) headCalls=headCalls+1; lastHeadReach=reach; if high and reach>=wallDistance then return {Distance=wallDistance} end end,
    Detour=function() searches=searches+1;return nil end}
geom.RecoveryExitClear=function(foot,height,goal,ray)
    return geom.HeadClear(foot,height,goal+Vector3.yAxis*.1,ray) and geom.HeadObstacle(foot,height,goal,G.Horizontal(goal-foot).Magnitude,ray)==nil
end
local Watchdog=assert(loadfile(arg[3]))()
local Blocked=assert(loadfile(arg[4]))()
local Speed=assert(loadfile(arg[5]))()
local modules={MonsterBlockedPursuit=Blocked,MonsterNavigationSpeed=Speed,MonsterBlockedRetreatGeometry={FindPoint=function(_,p,g,d) return g+(p-g).Unit*d end},MonsterStuckWatchdog=Watchdog,MonsterNavigationTrace=trace,MonsterNavigationConfig={recheckSeconds=1,sampleSeconds=1,stuckPercent=50,searchDistance=40,stuckReturnSeconds=30,blockedRetreatBuffer=2,blockedRetreatSpeedMultiplier=1,blockedReengageSpeedMultiplier=1.5,rescueRouteSpeedMultiplier=1.5,bowRange=40},MonsterRecoveryGeometry=geom,
    MonsterRescueGraph={Find=function() return nil end},MonsterClimbMotion={Stop=function() end},MonsterDeathChasePolicy={AllowsPursuitPosition=function() return true end},ActorHomeLeash={Outside=function() return false end}}
local parent={WaitForChild=function(_,n) return n end}
parent.Parent={WaitForChild=function() return parent end}
script={Parent=parent};require=function(n) return assert(modules[n],n) end
local N=assert(loadfile(arg[2]))()
local target=v(0,0,10)
N.NavigateTo(agent,target,10)
assert(attrs.MonsterRecoveryMode=='Direct' and #commands==1)
high=true;wallDistance=4;t=1.1;N.NavigateTo(agent,target,10)
assert(attrs.MonsterRecoveryMode=='Retry' and attrs.MonsterLastRecoveryEvent=='NoAccessiblePlan')
assert(attrs.MonsterRecoveryActualSpeed==0 and attrs.MonsterRecoveryExpectedSpeed==10)
assert(searches==1 and #commands==2 and commands[2].Magnitude==0)
t=2.7;N.NavigateTo(agent,target,10)
assert(attrs.MonsterRecoveryMode=='Retry' and searches==1 and #commands==2,'no second full search or move into blocked target')
for _,tick in ipairs({4.3,5.9,7.5,9.1}) do
    t=tick; N.NavigateTo(agent,target,10)
    assert(searches==1 and #commands==2,'M588 no repeated failed calculation')
end
high=false;isClear=true;t=10.7;N.NavigateTo(agent,target,10)
assert(attrs.MonsterRecoveryMode=='Direct' and #commands==3 and commands[3].Z==10,'resume when path opens')
print('M564 navigation retry state machine passed')

-- M566: a high wall triggers recovery before a single Direct movement.
N.Clear(agent); root.Position=v(0,0,0); commands={}; t=10; isClear=false; high=true;wallDistance=2
local entry,corner,exit=v(5,0,0),v(5,0,6),v(0,0,8)
local entryCalls=0
geom.RouteEntryClear=function(a,b,params)
    entryCalls=entryCalls+1
    assert((a-root.Position).Magnitude==0 and b==entry and params)
    return true
end
modules.MonsterRescueGraph.Find=function(start,_,connect)
    assert(connect(start,entry),'Graph uses the foot entry helper')
    return {points={entry,corner,exit},cost=15}
end
local h0, f0=headCalls,heelCalls
N.NavigateTo(agent,target,10)
assert(attrs.MonsterRecoveryMode=='RescueRoute' and attrs.MonsterRecoveryPlanIndex==1)
assert(#commands==1 and commands[1].X==5,'no direct move into high wall')
assert(agent.humanoid.WalkSpeed==15,'route approach is boosted from first MoveTo')
assert(entryCalls==1,'one foot-only entry check')
assert(headCalls==h0+1 and heelCalls==f0,'Direct head ray first; no heel ray')
-- Diagonal heel ray clear but horizontal gate blocked: cannot release.
isClear=true; t=11.1;root.Position=v(3.5,0,0);N.NavigateTo(agent,target,4)
assert(attrs.MonsterRecoveryMode=='RescueRoute' and commands[#commands].X==5,'horizontal hit vetoes clear heel ray')
-- A single pair of clear rays releases immediately, even before the entry.
high=false; t=12.2;root.Position=v(3.8,0,0);N.NavigateTo(agent,target,.1)
assert(attrs.MonsterRecoveryMode=='Direct' and attrs.MonsterLastRecoveryEvent=='DirectPathClear')
assert(commands[#commands].Z==10,'no entry lock or second confirmation')
-- A blocked heel ray short-circuits the horizontal recheck.
N.Clear(agent);root.Position=v(0,0,0);commands={};t=20;high=true;isClear=false
N.NavigateTo(agent,target,10);h0=headCalls;f0=heelCalls
t=21.1;root.Position=v(4,0,0);N.NavigateTo(agent,target,10)
assert(attrs.MonsterRecoveryMode=='RescueRoute' and attrs.MonsterRecoveryPlanIndex==2)
assert(headCalls==h0 and heelCalls==f0+1,'blocked heel ray avoids another cast')
-- End of the route with live obstruction stays stopped.
t=22.2;root.Position=corner;N.NavigateTo(agent,target,10)
t=23.3;root.Position=exit;N.NavigateTo(agent,target,10)
assert(attrs.MonsterRecoveryMode=='Retry' and attrs.MonsterLastRecoveryEvent=='RouteExitBlocked')
assert((commands[#commands]-exit).Magnitude==0,'no direct charge after final waypoint')
-- Both casts clear after retry => move straight again.
isClear=true;high=false;t=25;N.NavigateTo(agent,target,10)
assert(attrs.MonsterRecoveryMode=='Direct' and commands[#commands].Z==10)
print('M566 primary gate, heel recheck, early exit and blocked completion passed')

-- On a live target, the heel endpoint is the bottom of its own collider,
-- not the monster's height or the centre of the target.
N.Clear(agent);root.Position=v(0,0,0);commands={};t=30;high=false;isClear=false
agent.returning=false
local collider={Position=v(0,8,10),Size=v(2,6,2),IsA=function(_,name) return name=='BasePart' end}
agent.target={FindFirstChild=function(_,n) if n=='RootCollider' then return collider end end}
expectedHeelY=5.1
N.NavigateTo(agent,target,10);h0=headCalls;f0=heelCalls
-- No cast every AI tick, only the configured interval.
t=30.2;root.Position=v(0,0,1);N.NavigateTo(agent,target,10)
assert(headCalls==h0 and heelCalls==f0)
-- A wall enters the attack radius before we are stuck.
t=31.1;root.Position=v(0,0,7);high=true;N.NavigateTo(agent,target,10)
assert(attrs.MonsterRecoveryMode=='RescueRoute' and headCalls==h0+1)
t=32.2;root.Position=v(2,0,5);N.NavigateTo(agent,target,5)
assert(heelCalls==f0+1,'uses live target collider heel')
print('M566 periodic primary gate and target collider heel passed')

-- M573: failed physical lift may have clear head and heel rays over a low lip.
-- The retained foot contact still prohibits Direct during the retry cooldown.
N.Clear(agent); agent.returning=true; agent.target=nil; root.Position=v(0,0,0);commands={};t=40
isClear=true;high=false;expectedHeelY=.1
modules.MonsterRescueGraph.Find=function() return nil end
local low=true
local landing=v(0,2,3)
geom.ProbeClimb=function()
    if low then return landing,2,'Ray',nil,{Distance=.6} end
    return nil,nil,'Ray'
end
modules.MonsterClimbMotion.Begin=function(_,state,p) state.climb={landing=p};return true end
modules.MonsterClimbMotion.Step=function() return 'Failed' end
modules.MonsterClimbMotion.Stop=function(state) state.climb=nil end
N.NavigateTo(agent,target,10)
t=41.1; N.NavigateTo(agent,target,10)
assert(attrs.MonsterRecoveryMode=='Climb')
t=41.2; N.NavigateTo(agent,target,10)
assert(attrs.MonsterRecoveryMode=='Retry' and attrs.MonsterLastRecoveryEvent=='ClimbFailed')
t=43; N.NavigateTo(agent,target,10)
assert(attrs.MonsterRecoveryMode=='Climb','low lip retries without failed-route cooldown')
t=43.1; N.NavigateTo(agent,target,10)
low=false;t=45; N.NavigateTo(agent,target,10)
assert(attrs.MonsterRecoveryMode=='Direct' and commands[#commands].Z==10,'removed low obstacle releases retry')
print('M573 failed climb retry gate passed')

-- M574: do not release an active route when the wall is outside attack range.
N.Clear(agent);root.Position=v(0,0,0);commands={};t=60;high=true;wallDistance=2;isClear=true
geom.ProbeClimb=function() return nil,nil,'Ray',high and {Distance=wallDistance} or nil end
modules.MonsterRescueGraph.Find=function() return {points={v(5,0,0),v(5,0,30),v(0,12,45)},cost=60} end
local far=v(0,12,50);expectedHeelY=12.1
N.NavigateTo(agent,far,10)
assert(attrs.MonsterRecoveryMode=='RescueRoute')
wallDistance=20;t=61.1;root.Position=v(4,0,0)
N.NavigateTo(agent,far,10)
assert(attrs.MonsterRecoveryMode=='RescueRoute' and lastHeadReach>50 and commands[#commands].X==5,'visible heels do not abandon route into distant wall')
high=false;t=62.2;root.Position=v(5,0,10);N.NavigateTo(agent,far,10)
assert(attrs.MonsterRecoveryMode=='Direct' and commands[#commands].Z==50,'clear full-length gate releases route')
print('M574 actual navigation retains recovery on distant wall')

-- M575: retry/replanning does not restart the chase-level watchdog.
N.Clear(agent);agent.returning=false;agent.target=nil;root.Position=v(0,0,0);commands={};t=100
high=true;wallDistance=2;isClear=false;expectedHeelY=.1
modules.MonsterRescueGraph.Find=function() return nil end
assert(N.NavigateTo(agent,target,10)==nil and attrs.MonsterRecoveryMode=='Retry')
for i=1,29 do
    t=100+i; assert(N.NavigateTo(agent,target,10)==nil,'no early return')
end
t=130;assert(N.NavigateTo(agent,target,10)=='StuckTimeout')
assert(attrs.MonsterRecoveryStuckSeconds==30)
-- M580: Return starts a fresh watchdog and can request a home recall if stuck.
N.Clear(agent);agent.returning=true;t=131
assert(N.NavigateTo(agent,target,10)==nil)
t=160;assert(N.NavigateTo(agent,target,10)==nil)
t=161;assert(N.NavigateTo(agent,target,10)=='StuckTimeout')
assert(attrs.MonsterRecoveryStuckSeconds==30)
print('M580 chase and return timeouts propagate to AI')

-- M576: a clear horizontal head ray + low measured speed must bypass BOTH
-- planners, even if they would offer an arbitrarily cheap alternative.
N.Clear(agent);agent.returning=true;root.Position=v(0,0,0);commands={};t=200
high=false;isClear=true;expectedHeelY=.1
local began=0
local lastLanding,lastRise,lastSpeed
modules.MonsterClimbMotion.Begin=function(_,state,p,rise,_,_,speed)
    began=began+1;lastLanding=p;lastRise=rise;lastSpeed=speed;state.climb={landing=p};return true
end
modules.MonsterClimbMotion.Step=function() return 'Done' end
geom.Detour=function() error('low obstacle must not scan detour') end
modules.MonsterRescueGraph.Find=function() error('low obstacle must not search graph') end
geom.ProbeClimb=function() return landing,2,'Ray',nil,{Distance=.6} end
N.NavigateTo(agent,target,10)
t=201.1;N.NavigateTo(agent,target,10)
assert(began==1 and attrs.MonsterRecoveryMode=='Climb' and lastLanding==landing and lastRise==2 and lastSpeed==10)
assert(attrs.MonsterLastRecoveryEvent=='LowClimbSelected')
-- No top sample: physical jump still starts without a route search.
N.Clear(agent);t=210;root.Position=v(0,0,0)
geom.ProbeClimb=function() return nil,nil,'Ray',nil,{Distance=.6} end
N.NavigateTo(agent,target,10);t=211.1;N.NavigateTo(agent,target,10)
assert(began==2 and lastRise==.25 and lastLanding.Z==1.5 and attrs.MonsterRecoveryMode=='Climb')
-- When following a route, a low obstruction triggers the same primitive and
-- does not replace the chosen route. A blocked heel ray retains the plan.
N.Clear(agent);t=220;root.Position=v(0,0,0);high=true;isClear=false
geom.Detour=function() return nil end
modules.MonsterRescueGraph.Find=function() return {points={v(5,0,0),v(5,0,6)},cost=20} end
geom.ProbeClimb=function() return nil,nil,'Ray',{Distance=2},{Distance=2} end
N.NavigateTo(agent,target,10)
assert(attrs.MonsterRecoveryMode=='RescueRoute')
local route=agent.recoveryNavigation.plan
geom.ProbeClimb=function() return landing,2,'Ray',nil,{Distance=.6} end
geom.Detour=function() error('route low obstacle must not scan detour') end
modules.MonsterRescueGraph.Find=function() error('route low obstacle must not search graph') end
t=221.1;N.NavigateTo(agent,target,10)
assert(began==3 and attrs.MonsterRecoveryMode=='Climb' and agent.recoveryNavigation.plan==route and lastSpeed==15)
print('M578 immediate low jump, forward speed, fallback and retained route passed')

-- M591 actual navigation: no graph retries in retreat/wait, no clock before wait,
-- fixed database bow radius triggers a fresh approach, and only waiting expires it.
N.Clear(agent);agent.returning=false;root.Position=v(0,0,0);commands={};t=300
local weaponRadius=7
local equippedType="sword"
agent.target={FindFirstChild=function() return nil end,FindFirstChildOfClass=function() return nil end,
    GetAttribute=function(_,k)
        if k=="AttackRadius" then return weaponRadius end
        if k=="EquippedWeaponType" then return equippedType end
    end}
geom.Detour=function() searches=searches+1;return nil end
modules.MonsterRescueGraph.Find=function() return nil end
geom.ProbeClimb=function() return nil,nil,'Ray',{Distance=2},{Distance=2} end
high=true;isClear=false;wallDistance=2;expectedHeelY=.1
local n=searches
N.NavigateTo(agent,target,10)
assert(attrs.MonsterRecoveryMode=='BlockedRetreat' and searches==n+1)
t=301;N.NavigateTo(agent,target,10)
assert(commands[#commands].Z==-32 and agent.humanoid.WalkSpeed==10)
root.Position=v(0,0,-32);t=310;N.NavigateTo(agent,target,10)
assert(attrs.MonsterRecoveryMode=='BlockedWait' and attrs.MonsterRecoveryStuckSeconds==0 and agent.lastDamageAt==310)
-- Switching equipment in Wait must neither change range nor restart the clock.
for i,tick in ipairs({311,325,339}) do
    weaponRadius=({40,3,7})[i];equippedType=({"bow","","sword"})[i]
    t=tick;assert(N.NavigateTo(agent,target,10)==nil)
end
assert(searches==n+1 and attrs.MonsterRecoveryStuckSeconds==29)
-- Player enters bow range even with sword equipped, normal direct path available.
t=339.5;high=false;isClear=true;N.NavigateTo(agent,v(0,0,7),10)
assert(attrs.MonsterRecoveryMode=='Direct' and agent.humanoid.WalkSpeed==15 and agent.lastDamageAt==339.5)
assert(searches==n+1)
-- Another encounter, already outside the range: wait immediately and recall only after 30s.
N.Clear(agent);root.Position=v(0,0,-33);high=true;isClear=false;t=400
weaponRadius=3;equippedType=""
N.NavigateTo(agent,target,10);t=401;N.NavigateTo(agent,target,10)
assert(attrs.MonsterRecoveryMode=='BlockedWait')
t=430;assert(N.NavigateTo(agent,target,10)==nil)
t=431;assert(N.NavigateTo(agent,target,10)=='StuckTimeout')
print('M591 blocked pursuit integration passed')
