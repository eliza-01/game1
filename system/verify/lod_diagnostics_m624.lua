-- Production diagnostics/queue/job/work loaded under plain Lua; engine work
-- and time are mocked. No Roblox CPU/FPS claims from this oracle.
local Capture = dofile('src/client/world/LodDiagnostics.luau')
local Queue = dofile('src/client/world/LodTransitionQueue.luau')
local Work = dofile('src/client/world/LodRuntimeWork.luau')
local Job = dofile('src/client/world/LodAssemblyJob.luau')
local now = 10
local d = Capture.new(function() return now end)
assert(not d.enabled)
d:Add('meshClones')
assert(d.counts == nil)
d:Start({prototypeRefreshes=3,contractChecks=2,retryScans=1})
local q = Queue.new(function(entries) table.sort(entries,function(a,b) return a.record.order<b.record.order end) end)
q.diagnostics=d
local work=Work.new(); work.diagnostics=d
local r={desired='FULL',actual='UNLOADED',order=1,diagnosticDesiredAt=now}
local r2={desired='FULL',actual='UNLOADED',order=2,diagnosticDesiredAt=now}
local pos={}
q:Begin(pos,false); q:Set(r,'FULL'); q:Set(r2,'FULL')
local function distance() end
work:Begin(q:Ordered(distance))
assert(d.counts.localSorts==1 and d.peaks.queueSize==2)
local callbacks={}
function callbacks.valid(entry) return q.entries[entry.record]==entry end
function callbacks.prepare(entry)
    return Job.new(function(job)
        for _=1,16 do
            job:Own({Destroy=function() end},'meshClones')
            job:Unit()
        end
    end)
end
function callbacks.commit(entry,job)
    entry.record.actual=entry.variant
    if job then job:Release() end
    q:Remove(entry.record)
    return true
end
function callbacks.failed() error('unexpected failed work') end
now=10.1; d:Frame(.016,work:Step(callbacks),.001)
assert(work.active and d.counts.meshClones>0)
q:Remove(r); now=10.2
work:Begin(q:Ordered(distance)); d:Frame(.020,work:Step(callbacks),.002)
assert(d.counts.staleJobCancels==1 and d.counts.cancelledJobs==1)
for _=1,10 do now=now+.01; d:Frame(.010,work:Step(callbacks),.001) end
assert(r2.actual=='FULL' and d.counts.commits==1)
assert(d.peaks.buildUnits<=Work.BuildBudget and d.peaks.cleanupUnits<=Work.CleanupBudget)
assert(d.counts.meshClones>=16 and d.peaks.stagingInstances>=16)
local report=d:Finish({prototypeRefreshes=5,contractChecks=2,retryScans=2},{placements=2})
assert(report.counters.prototypeRefreshes==2 and report.counters.contractChecks==0 and report.counters.retryScans==1)
assert(report.heartbeatMs.count==12 and report.heartbeatMs.p99==20)
assert(report.callbackElapsedMs.p99==2)
assert(report.queueResidenceMs.count==1 and report.desiredToActualMs.count==1)
assert(report.queueResidenceMs.mean>0 and report.desiredToActualMs.mean>0)
assert(not d.enabled and d:Finish({}, {})==nil)
d:Add('meshClones'); assert(report.counters.meshClones==d.counts.meshClones)
d:Start({})
for i=1,12001 do d:Frame(.010,{build=0,cleanup=0,commit=0},.001) end
local bounded=d:Finish({}, {})
assert(bounded.heartbeatMs.count==12001 and bounded.heartbeatMs.sampled==12000)
assert(bounded.callbackElapsedMs.sampled==12000 and bounded.counters.meshClones==0)
assert(bounded.desiredToActualMs.count==0)
print('M624 diagnostic capture: disabled, counters, queue/desired latency, stale cancel, budgets, bounded samples, reset PASS')
