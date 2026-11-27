-- Real queue + production cadence policy, fake model attributes and clock.
local Queue = dofile('src/server/actor/ActorAIScheduleQueue.luau')
local config = {enabled=true,dormantSeconds=2}
local stub = {}; function stub:WaitForChild() return self end
local env = setmetatable({game={GetService=function() return stub end}, require=function() return {AdaptiveAISettings=function() return config end} end, table=setmetatable({freeze=function(t) return t end},{__index=table})},{__index=_G})
local Policy = assert(loadfile('src/server/actor/ActorActivityPolicy.luau','t',env))()
local function agent()
    local attrs={LifeState='Alive',MonsterAggressive=true}
    local model={Parent=true,GetAttribute=function(_,k) return attrs[k] end}
    local pos=setmetatable({}, {__sub=function() return {Magnitude=0} end})
    return {active=true,model=model,state='Idle',nextTargetScanAt=.3,root={Anchored=true,Position=pos},home={Position=pos},recovery={Pending=function() return false end}},attrs
end
local m,a=agent()
assert(Policy.Enabled and Policy.MonsterDelay(m,0,.1)==.3)
assert(math.abs(Policy.MonsterDelay(m,.15,.1)-.15)<1e-8)
a.MonsterAggressive=false; assert(Policy.MonsterDelay(m,0,.1)==2)
for _,field in ipairs({'target','attacking','returning','retaliating','homeRecall','specialCast','retreatPending','attackPursuitActive'}) do
    m[field]=true; assert(Policy.MonsterDelay(m,0,.1)==.1,field); m[field]=nil
end
for _,state in ipairs({'Chase','Attack','Return','Aggro','Retreat','BlockedWait','Climb','Retry','RescueRoute','HomeRecall'}) do
    m.state=state; assert(Policy.MonsterDelay(m,0,.1)==.1,state)
end
m.state='Idle'
for _,attr in ipairs({'MonsterCombatActive','MonsterSpawning'}) do a[attr]=true; assert(Policy.MonsterDelay(m,0,.1)==.1); a[attr]=nil end
for _,nav in ipairs({{plan={}},{climb={}},{blockedPursuit={}},{mode='Retry'},{mode='BlockedWait'}}) do m.recoveryNavigation=nav; assert(Policy.MonsterDelay(m,0,.1)==.1) end
m.recoveryNavigation=nil
assert(Policy.NpcDelay(m,0,.1)==2)
m.root.Anchored=false; assert(Policy.NpcDelay(m,0,.1)==.1); m.root.Anchored=true
m.recovery.Pending=function() return true end; assert(Policy.NpcDelay(m,0,.1)==.1); m.recovery.Pending=function() return false end
m.root.Position=setmetatable({}, {__sub=function() return {Magnitude=10} end}); assert(Policy.NpcDelay(m,0,.1)==.1)
local now=0; local count=0; local errors=0
local q=Queue.new(function() return now end,function(f,...) f(...) end,function() errors=errors+1 end)
local function pump(t) now=t; q:Pump(t) end
local function step(k,t) count=count+1; k.nextTargetScanAt=t+.3 end
q:Register(m,.1,.1,step,nil,false,Policy.MonsterDelay)
pump(.1); assert(count==1 and q.heap[1].due==2.1)
pump(.2); assert(count==1)
m.target={}; q:Wake(m); assert(math.abs(q.heap[1].due-.3)<1e-8)
q:Wake(m); assert(#q.heap==1)
pump(.31); assert(count==2 and not q.entries[m].deferred)
local deadline=q.heap[1].due; q:Wake(m); assert(q.heap[1].due==deadline)
pump(.42); assert(count==3)
m.target=nil; a.MonsterAggressive=true
pump(.53); assert(count==4 and math.abs(q.heap[1].due-.83)<1e-8)
pump(.82); assert(count==4); pump(.84); assert(count==5)
q:Remove(m); assert(#q.heap==0); q:Wake(m); assert(#q.heap==0)
-- Bad policy falls back to old cadence, without losing the agent.
q:Register(m,.1,.1,step,nil,false,function() error('policy failure') end)
pump(1); assert(errors==1 and q.entries[m] and q.heap[1].due==1.1)
q:Remove(m)
-- Wake during yielding dispatch does not duplicate or resurrect a removed step.
local thread; local y=Queue.new(function() return now end,function(f,...) thread=coroutine.create(f); assert(coroutine.resume(thread,...)) end,function(e) error(e) end)
y:Register(m,.1,.1,function() coroutine.yield() end,nil,false,Policy.MonsterDelay)
now=2; y:Pump(now); y:Wake(m); assert(#y.heap==0); y:Remove(m); assert(coroutine.resume(thread)); assert(#y.heap==0)
print('Adaptive AI: protected states, scan deadline, passive/NPC safety, wake, removal, error fallback OK')
