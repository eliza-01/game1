-- Executable shared index/threshold and async acquisition lifecycle oracle.
local Requests = dofile('src/client/world/HouseMeshRequests.luau')
local Index = dofile('src/client/world/StaticPlacementIndex.luau')
local Cache = dofile('src/client/world/LodThresholdCache.luau')
local Candidates = dofile('src/client/world/LocationLodCandidates.luau')
local Queue = dofile('src/client/world/LodTransitionQueue.luau')
local Job = dofile('src/client/world/LodAssemblyJob.luau')
local Work = dofile('src/client/world/LodRuntimeWork.luau')
local time, pending, disposed, failures = 0, {}, 0, 0
local fail = false
local function mesh()
    local part = {destroyed=false}
    function part:Destroy() assert(not self.destroyed); self.destroyed=true; disposed=disposed+1 end
    function part:IsA(name) return name=='MeshPart' end
    return part
end
local requests=Requests.new(function() return time end,function(fn) pending[#pending+1]=fn end,
    function() if fail then error('load failed') end; return mesh() end,
    function(part) part:Destroy() end,function() failures=failures+1 end)
local function complete() local fn=table.remove(pending,1); assert(fn); fn() end
local function record() return {generation=0, desired='FULL', proxy={}} end
local function start(r)
    local proxy=r.proxy
    return requests:TakeOrStart(r,function(ticket) return r.generation==ticket and r.desired=='FULL' and r.proxy==proxy end)
end
local a,b,c,d,e=record(),record(),record(),record(),record()
for _,r in ipairs({a,b,c,d,e}) do assert(start(r)==nil) end
assert(requests.count==4 and #pending==4)
complete(); assert(requests.count==4) -- completed detached still owns a slot
assert(start(e)==nil and #pending==3)
local part=start(a); assert(part and requests.count==3 and not part.Parent)
local work=Work.new()
local job=Job.new(function(j) j.bundle=part; j:Unit() end); job:Own(part)
work.active={job=job}; work:Cancel(); work:Cleanup(8); assert(part.destroyed)
assert(start(e)==nil and requests.count==4)
b.generation=1; requests:Invalidate(b); assert(requests.count==4)
complete(); assert(requests.count==3) -- obsolete in-flight return disposed
complete(); c.proxy={}; requests:Prune(c); assert(requests.count==2) -- ready proxy replaced
complete(); d.desired='LOD1'; requests:Invalidate(d); assert(requests.count==1)
complete(); e.proxy={}; assert(start(e)==nil and #pending==1) -- old result disposed, fresh request allowed
complete(); local fresh=start(e); assert(fresh); fresh:Destroy()
assert(requests.count==0)
fail=true; start(a); complete(); assert(failures==1 and a.retryAt==15)
assert(start(a)==nil and #pending==0)
time=15; fail=false; start(a); assert(#pending==1)
requests:Destroy(); complete(); assert(requests.count==0 and next(requests.slots)==nil)
assert(disposed==7, 'expected exact detached ownership cleanup: '..disposed)

-- Actual production policy, adapting only Luau syntax for Lua 5.3. A rotated
-- box distance oracle supplies Vector3/CFrame operations, including Y and scale.
local f=assert(io.open('src/shared/world/LocationLodDistancePolicy.luau'))
local source=f:read('*a'); f:close()
source=assert(source:match('^(.-)%-%- Single%-mesh visibility tier'))
source=source:gsub('index %+= 1','index = index + 1'):gsub('index %-=%s*1','index = index - 1')
source=source:gsub('if config.mode == "lod1"%s+then ({.-}) else ({.-})','(config.mode == "lod1" and %1 or %2)')
source=source:gsub('if config.mode == "lod1" then ({.-}) else ({.-})','(config.mode == "lod1" and %1 or %2)')
table.freeze=table.freeze or function(t) return t end
local mt={}
local function v(x,y,z) return setmetatable({X=x,Y=y,Z=z,Magnitude=math.sqrt(x*x+y*y+z*z)},mt) end
mt.__sub=function(a,b) return v(a.X-b.X,a.Y-b.Y,a.Z-b.Z) end
mt.__mul=function(a,b) return v(a.X*b,a.Y*b,a.Z*b) end
mt.__eq=function(a,b) return a.X==b.X and a.Y==b.Y and a.Z==b.Z end
Vector3={new=v}
local policy=assert(load(source..'\nreturn Policy'))()
local function house(i,center,size,angle,mode)
    local frame={PointToObjectSpace=function(_,p) local q=p-center; return v(q.X*math.cos(angle)+q.Z*math.sin(angle),q.Y,-q.X*math.sin(angle)+q.Z*math.cos(angle)) end}
    return {house=true,order=i,pivot=center,worldFrame=frame,worldSize=size,mode=mode,
        distances={mode=mode,lod1=100,hide=400,hysteresis=10},actual='UNLOADED'}
end
local records={house(1,v(0,0,0),v(1000,20,50),math.pi/4,'lod1'),house(2,v(-1000,300,0),v(40,300,40),0,'full'),
    {order=3,pivot=v(0,0,0),mode='lod2',distances={lod1=100,lod2=200,hide=400,hysteresis=10},actual='UNLOADED'}}
local candidates=Candidates.new(Index.new(records)); local oracle={}
local positions={v(550,0,550),v(600,0,600),v(0,0,0),v(0,111,0),v(0,111,0),v(-1000,0,0),v(10000,10000,0),v(0,0,0)}
for _,pos in ipairs(positions) do
    local localRecords=candidates:Collect(pos)
    for _,r in ipairs(localRecords) do Cache.Resolve(r,pos,policy,false) end
    candidates:Retain(localRecords)
    for _,r in ipairs(records) do
        local dist=Cache.Measure(r,pos,policy)
        oracle[r]=Cache.ResolveAt(r,dist,policy,oracle[r])
        assert((r.desired or 'UNLOADED')==oracle[r],'mixed index lost record '..r.order)
        if r.mode=='full' then assert(r.desired~='LOD1') end
    end
end
local q=Queue.new(Candidates.SortTransitions)
q:Begin(v(0,0,0)); for _,r in ipairs(records) do q:Set(r,'FULL') end
local ordered=q:Ordered(function(r,p) return Cache.Distance(r,p,policy) end)
assert(#ordered==3 and ordered[1].record==records[1] and ordered[2].record==records[3])
print('M623 mixed index, house thresholds, detached async slots and lifecycle PASS')
