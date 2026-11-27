-- Executes the actual consumer bodies under a small Lua mock. Strip only the
-- known Luau type annotations and compound increments; not a Roblox simulation.
local now, moves, nativeStarts, destroyed = 0, {}, 0, 0
local threads = {}
local function spawn(fn)
    local t=coroutine.create(fn); threads[#threads+1]=t; assert(coroutine.resume(t))
end
local vecmt={}
local function vec(x,y,z) return setmetatable({X=x,Y=y,Z=z},vecmt) end
vecmt.__sub=function(a,b) return vec(a.X-b.X,a.Y-b.Y,a.Z-b.Z) end
vecmt.__index=function(v,k) if k=='Magnitude' then return math.sqrt(v.X*v.X+v.Y*v.Y+v.Z*v.Z) end end
local zero=vec(0,0,0)
local Vector3={new=vec,zero=zero}
local enum={PathStatus={Success='Success'}}
local services={}
local rootnode={}; rootnode.Parent=rootnode
function rootnode:WaitForChild(name) return name end
services.ReplicatedStorage={WaitForChild=function() return rootnode end}
local failNext=false
services.PathfindingService={CreatePath=function(_,params)
    assert(params.AgentRadius==1 and params.AgentHeight==4 and params.AgentCanJump==false and params.WaypointSpacing==3)
    local path={Status='Success',Blocked={Connect=function() return {Disconnect=function() end} end}}
    function path:ComputeAsync(origin,goal)
        nativeStarts=nativeStarts+1; self.origin,self.goal=origin,goal
        local fail=failNext; failNext=false
        coroutine.yield()
        if fail then self.Status='NoPath' end
    end
    function path:GetWaypoints() return {{Position=self.origin},{Position=self.goal}} end
    function path:Destroy() assert(not self.destroyed); self.destroyed=true; destroyed=destroyed+1 end
    return path
end}
local modules={NavigationRequestQueue=dofile('src/server/actor/NavigationRequestQueue.luau'),GameOptions={NavigationBudgetSettings=function() return {concurrent=2,startsPerSecond=8} end},MonsterTargetPolicy={HorizontalDistance=function(a,b) return vec(a.X-b.X,0,a.Z-b.Z).Magnitude end}}
local node={}; node.Parent=node
function node:WaitForChild(name) if name=='actor' or name=='character' then return self end; return name end
services.ReplicatedStorage={WaitForChild=function() return node end}
local env=setmetatable({script={Parent=node},game={GetService=function(_,name) return services[name] end},Vector3=Vector3,Enum=enum,task={spawn=spawn},os={clock=function() return now end},table=setmetatable({freeze=function(v) return v end},{__index=table}),warn=function() end,require=function(name) return assert(modules[name] or (name=='CharacterMovementConfig' and {}),tostring(name)) end},{__index=_G})
local function loadModule(path)
    local file=assert(io.open(path)); local source=file:read('*a'); file:close()
    for _,typeName in ipairs({'any','number','Vector3','BasePart','Humanoid'}) do source=source:gsub(': '..typeName..'%f[%W]','') end
    source=source:gsub('([%w_%.]+) %+= (%d+)','%1 = %1 + %2')
    return assert(load(source,'@'..path,'t',env))()
end
local budget=loadModule('src/server/actor/NavigationScheduler.luau'); modules.NavigationScheduler=budget
local monster=loadModule('src/server/monster/MonsterChaseNavigation.luau')
local npc=loadModule('src/server/actor/ActorChaseNavigator.luau')
local function actor()
    local humanoid={Parent=true,Move=function() end,MoveTo=function(self,p) moves[#moves+1]=p; self.last=p end}
    return {active=true,root={Parent=true,Position=zero},humanoid=humanoid,target={}}
end
local a=actor(); monster.Initialize(a)
local goal=vec(20,0,0)
monster.NavigateTo(a,goal,13); now=1; monster.NavigateTo(a,goal,13)
assert(a.pathRequest and a.humanoid.last==zero)
budget.Pump(); assert(nativeStarts==1)
-- During a yielding ComputeAsync, entering attack/stop prevents late MoveTo.
monster.StopNavigation(a); local count=#moves; assert(coroutine.resume(threads[1])); assert(#moves==count and destroyed==1)
-- NPC starts, queues latest goal, then consumes on its next decision only.
local b=actor(); local nav=npc.new(b.root,b.humanoid)
nav:Chase(goal,13); now=2; nav:Chase(goal,13); assert(nav.pathRequest)
local updated=vec(30,0,0); nav:Chase(updated,13); budget.Pump(); assert(nativeStarts==2)
count=#moves; assert(coroutine.resume(threads[2])); assert(#moves==count)
nav:Chase(updated,19); assert(b.humanoid.last==updated and b.humanoid.WalkSpeed==19)
nav:Stop(); assert(destroyed==2)
-- A moved goal while running must not issue a stale waypoint or direct fallback.
nav:Chase(goal,13); now=3; nav:Chase(goal,13); budget.Pump(); assert(nativeStarts==3)
assert(coroutine.resume(threads[3])); nav:Chase(updated,13); assert(nav.pathRequest and b.humanoid.last==zero and destroyed==3)
-- A genuine NoPath result retains the existing direct fallback.
now=4; failNext=true; budget.Pump(); assert(coroutine.resume(threads[4])); nav:Chase(updated,13)
assert(b.humanoid.last==updated and nav.mode=='Direct' and destroyed==4)
nav:Destroy()
print('Native consumer Lua mock: cancel, latest queued destination, stale result, direct fallback, current speed OK')
