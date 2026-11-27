local Priority = dofile('src/client/world/LodLoadPriority.luau')
local Candidates = dofile('src/client/world/LocationLodCandidates.luau')
local Queue = dofile('src/client/world/LodTransitionQueue.luau')
local Work = dofile('src/client/world/LodRuntimeWork.luau')
local Job = dofile('src/client/world/LodAssemblyJob.luau')
local Requests = dofile('src/client/world/HouseMeshRequests.luau')
local now, pos, calls = 0, 0, 0
local function surface(p, center, size)
    calls = calls + 1
    return math.max(0, math.abs(p-center)-size/2)
end
local function record(order, center, size, house)
    local r={order=order,desired='FULL',actual='UNLOADED',generation=0,house=house}
    if house then r.worldFrame=center; r.worldSize=size
    else r.fullBounds={{CFrame=center,Size=size}} end
    return r
end
-- The fence pivot is far away, but its surface is beside the player.
local fence=record(1,100,190,false)
fence.fullBounds[#fence.fullBounds+1]={CFrame=400,Size=10} -- nearest component, not union center
local second=record(2,15,2,false)
local house=record(3,80,10,true)
local distant=record(4,180,10,false)
local upgrade=record(5,1,1,false); upgrade.actual='LOD1'
local unload=record(6,500,1,false); unload.actual='FULL'; unload.desired='UNLOADED'
local missing=record(7,10,2,false) -- no queue entry until dependency appears
local records={distant,house,second,fence,upgrade,unload,missing}
local priority=Priority.new(function() return now end)
local q=Queue.new(Candidates.SortTransitions)
local work=Work.new()
local function sample(reset)
    q:Begin(pos,reset)
    for _,r in ipairs(records) do if r~=missing then q:Set(r,r.desired) end end
    priority:Observe(records,pos,surface,reset)
    local o=q:Ordered(function(r,p) return priority:Sample(r,p,surface) end)
    work:Begin(o,function(e) return priority:Allows(e.record) end)
    return o
end
local o=sample(true)
assert(o[1].record==unload and o[2].record==fence and o[3].record==second and o[4].record==upgrade)
assert(priority.frontier==0 and fence.loadDistance==5 and #work.builds==3 and #work.unloads==1)
assert(not priority:Allows(house) and not priority:Allows(distant))
local count=calls; sample(); assert(calls==count,'stationary surface distances recomputed')
-- Distant aging may not jump the near band.
for _=1,9 do q:Attempted(q.entries[fence]); sample() end
assert(q:Ordered(function() end)[2].record==second)
assert(#work.builds==3)
local callbacks={}
function callbacks.valid(e,job) return q.entries[e.record]==e and (e.variant=='UNLOADED' or priority:Allows(e.record)) end
function callbacks.prepare(e)
    if e.record==fence then return nil,'unavailable',true end
    return Job.new(function(j) j:Unit() end)
end
function callbacks.commit(e,j) if j then j:Release() end; e.record.actual=e.variant; q:Remove(e.record); return true end
function callbacks.failed(e,reason,retryable) assert(retryable) end
for _=1,8 do work:Step(callbacks) end
assert(second.actual=='FULL' and upgrade.actual=='FULL' and unload.actual=='UNLOADED')
assert(fence.actual=='UNLOADED' and house.actual=='UNLOADED' and distant.actual=='UNLOADED')
-- Progress renews the current band's grace. Missing (not queued) still gates.
now=3.9; sample(); assert(priority.frontier==0)
now=7.8; sample(); assert(priority.frontier==0)
now=8; sample(); assert(priority.frontier==2 and priority:Allows(house) and not priority:Allows(distant))
for _=1,8 do work:Step(callbacks) end
assert(house.actual=='FULL' and distant.actual=='UNLOADED')
now=8.1; sample(); assert(priority.frontier==5)
for _=1,8 do work:Step(callbacks) end
assert(distant.actual=='FULL')
-- A delayed prototype still gets priority when it appears, without reblocking.
q:Set(missing,'FULL'); o=sample(); assert(priority.frontier==nil and o[1].record==fence and o[2].record==missing)
-- A respawn / teleport resets the grace and anchors ordering at the new root.
fence.actual='UNLOADED'; house.actual='UNLOADED'; distant.actual='UNLOADED'; pos=180
sample(true); assert(priority.frontier==0 and priority:Allows(distant) and not priority:Allows(house))
work:Destroy()
-- An already-running far build must yield when a new nearer cold record appears.
local farEntry={record=distant,variant='FULL'}
local work2=Work.new()
local owned={destroyed=false,Destroy=function(self) self.destroyed=true end}
local cancelledJob=Job.new(function(j) j:Own(owned); for _=1,64 do j:Unit() end end)
work2.active={entry=farEntry,job=cancelledJob}; cancelledJob:Advance(1)
local gate=Priority.new(function() return now end)
gate:Observe({fence,distant},0,surface,true)
assert(not gate:Allows(distant))
work2:Step({valid=function(e) return gate:Allows(e.record) end})
assert(work2.active==nil and cancelledJob.state=='cancelled')
work2:Destroy(); assert(owned.destroyed)
-- Four async slots: only a completed distant result is released, not an engine call.
local pending, disposed = {},0
local requests=Requests.new(function() return now end,function(fn) pending[#pending+1]=fn end,
    function() return {} end,function() disposed=disposed+1 end,function() error('unexpected failure') end)
local rr={record(11,10,1,true),record(12,90,1,true),record(13,100,1,true),record(14,110,1,true)}
for _,r in ipairs(rr) do requests:TakeOrStart(r,function() return true end) end
assert(requests:Full()); requests:YieldReadyOutside(function() return false end); assert(requests.count==4 and disposed==0)
table.remove(pending,1)(); requests:YieldReadyOutside(function(r) return r==rr[1] end); assert(requests.count==4)
table.remove(pending,1)(); requests:YieldReadyOutside(function(r) return r==rr[1] end); assert(requests.count==3 and disposed==1)
requests:Destroy(); for _,fn in ipairs(pending) do fn() end; assert(requests.count==0 and disposed==4)
print('M626 near-band priority: surface, cold/upgrade, aging, async slots, missing dependency, stall, teleport PASS')
