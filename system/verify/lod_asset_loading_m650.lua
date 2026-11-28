-- Actual pure modules, asynchronous loader and geometry test doubles.
local Priority = dofile('src/client/world/LodLoadPriority.luau')
local Work = dofile('src/client/world/LodRuntimeWork.luau')
local Job = dofile('src/client/world/LodAssemblyJob.luau')
local Readiness = dofile('src/client/world/LodAssetReadiness.luau')
local Plan = dofile('src/server/world/LocationTemplateStagePlan.luau')
local now = 0
local function surface(p,c,s) return math.max(0,math.abs(p-c)-s/2) end
local function record(order, center, size)
    return {order=order, desired='FULL', actual='UNLOADED', fullBounds={{CFrame=center,Size=size}}}
end
local near, second, far = record(1,100,190), record(2,15,1), record(3,100,1)
local gate=Priority.new(function() return now end)
local active=nil
local function sample(pending)
    gate:Observe({far,second,near},0,surface,false,function(r) return active==r end,function() return pending end)
end
sample(true); assert(gate.frontier==0 and not gate:Allows(far))
now=5; sample(true); assert(not gate:Allows(far),'four seconds is not a real loading failure')
active=near
for t=10,50,5 do now=t; sample(true); assert(not gate:Allows(far),'active load must retain band') end
active=nil; near.actual='FULL'; now=51; sample(false)
assert(not gate:Allows(far))
second.actual='FULL'; now=52; sample(false); assert(gate:Allows(far))
-- Missing dependency grace is bounded, even with unfinished server staging.
near.actual='UNLOADED'; second.actual='UNLOADED'; gate:Observe({far,second,near},0,surface,true,nil,function() return true end)
now=81; sample(true); assert(not gate:Allows(far))
now=82; sample(true); assert(gate:Allows(far))
-- Work holds a detached job during resource fetch; unloads do not stall;
-- old actual remains untouched, and cancellation invalidates callback.
local scheduled, reports, commits, fetches = {},0,{},0
local fetchOK=true
local readiness=Readiness.new(function(bundle,current)
    fetches=fetches+1
    assert(bundle and current())
    return fetchOK,fetchOK
end,function(fn) scheduled[#scheduled+1]=fn end,function() return now end,function() reports=reports+1 end)
local work=Work.new()
local function entry(id,variant) return {record={id=id},variant=variant,valid=true} end
local a,b,u=entry('near','FULL'),entry('far','FULL'),entry('old','UNLOADED')
local cb={}
function cb.valid(e) return e.valid end
function cb.ready(e,j) return readiness:Ready(j) end
function cb.prepare(e) return Job.new(function(j) j.bundle={}; j:Unit() end) end
function cb.commit(e,j) commits[#commits+1]=e.record.id; if j then j:Release() end; e.valid=false; return true end
function cb.failed(e,reason) error(reason) end
work:Begin({a,b}); work:Step(cb)
assert(#scheduled==1 and #commits==0 and work.active.entry==a)
work:Begin({u,a,b}); work:Step(cb); work:Step(cb)
assert(#scheduled==1 and #commits==1 and commits[1]=='old')
table.remove(scheduled,1)(); work:Step(cb); assert(commits[2]=='near')
work:Step(cb); assert(work.active.entry==b and #scheduled==1)
local stale=work.active.job; b.valid=false; work:Step(cb)
table.remove(scheduled,1)(); assert(stale.state=='cancelled' and #commits==2 and fetches==1)
-- Failure is an explicit native fallback, not an infinite active job.
local c=entry('fallback','FULL'); fetchOK=false; work:Begin({c}); work:Step(cb)
local job=work.active.job; table.remove(scheduled,1)(); assert(job.assetFetch.done and not job.assetFetch.success and reports==1)
work:Step(cb); assert(commits[3]=='fallback'); work:Destroy()
-- One-dimensional frame doubles preserve the tested ordering and scaling.
local frameMT,vecMT={},{}
local function vector(x) return setmetatable({x=x},vecMT) end
local function frame(x) return setmetatable({x=type(x)=='table' and x.x or x},frameMT) end
vecMT.__mul=function(v,s) return vector(v.x*s) end
frameMT.__mul=function(a,b) return frame(a.x+b.x) end
frameMT.__index=function(t,k) if k=='Position' then return vector(t.x) elseif k=='Rotation' then return frame(0) end end
CFrame={new=frame}; Vector3={new=vector}
local manifest={targets={'distant','fence','near'},modes={distant='full',fence='lod1',near='full'},placements={
    {slug='distant',cframe={200},size={2}},
    {slug='fence',cframe={500},size={2},components={{cframe={100},size={190}}}},
    {slug='near',cframe={10},size={2}},
},houses={placements={{slug='house',pivot={15},scale=2},{slug='house',pivot={300},scale=2}},types={house={mode='lod1',parts={
    {cframe={2},size={3},lod1ModelAssetId='9'}, {cframe={4},size={3},lod1ModelAssetId='9'}, {cframe={0},size={1},lod1ModelAssetId=''}
}}}}}
local registry={assets={distant={modelAssetId='1'},fence={modelAssetId='2',lod1ModelAssetId='3'},near={modelAssetId='4'}}}
local rows=Plan.Build(manifest,registry,function(mode) if mode=='lod1' then return {'FULL','LOD1'} else return {'FULL'} end end,{0},function(p,c,s) return surface(p,c.x,s.x) end)
assert(#rows==5 and rows[1].name=='fence__FULL' and rows[1].parts==manifest.placements[2].components)
assert(rows[2].name=='near__FULL' and rows[3].name=='__HOUSE_PART_LOD1__9' and rows[3].distance==16)
assert(rows[4].name=='fence__LOD1' and rows[4].assembly and rows[5].name=='distant__FULL')
print('M650 near staging, long fetch, bounded missing grace, detached commit, unload, cancellation, failure fallback PASS')
