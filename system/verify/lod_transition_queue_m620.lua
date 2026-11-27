local Cache = dofile('src/client/world/LodThresholdCache.luau')
local Queue = dofile('src/client/world/LodTransitionQueue.luau')
local Candidates = dofile('src/client/world/LocationLodCandidates.luau')
local Index = dofile('src/client/world/StaticPlacementIndex.luau')
local f = assert(io.open('src/shared/world/LocationLodDistancePolicy.luau'))
local source = f:read('*a'); f:close()
source = assert(source:match('^(.-)%-%- Distance to the rotated visual bounds'))
source = source:gsub('index %+= 1', 'index = index + 1'):gsub('index %-=%s*1', 'index = index - 1')
table.freeze = table.freeze or function(t) return t end
local Policy = assert(load(source .. '\nreturn Policy'))()
local resolves, comparisons, samples = 0,0,0
local observed = {Resolve=function(...) resolves=resolves+1; return Policy.Resolve(...) end}
local mt = {}
local function v(x,y,z) return setmetatable({X=x,Y=y,Z=z},mt) end
mt.__eq=function(a,b) return a.X==b.X and a.Y==b.Y and a.Z==b.Z end
mt.__sub=function(a,b) return {Magnitude=math.sqrt((a.X-b.X)^2+(a.Y-b.Y)^2+(a.Z-b.Z)^2)} end
local function record(i,position,mode,h)
    return {order=i,pivot=position,mode=mode,distances={lod1=100,lod2=200,hide=400,hysteresis=h},actual='UNLOADED'}
end
local function trace(records, positions)
    local candidates = Candidates.new(Index.new(records))
    local oracle={}
    for tick,pos in ipairs(positions) do
        local active=candidates:Collect(pos)
        for _,r in ipairs(active) do Cache.Resolve(r,pos,observed,false) end
        candidates:Retain(active)
        for _,r in ipairs(records) do
            oracle[r]=Policy.Resolve((pos-r.pivot).Magnitude,oracle[r],r.distances,r.mode)
            assert((r.desired or 'UNLOADED')==oracle[r], 'threshold mismatch '..tick..'/'..r.order)
            comparisons=comparisons+1
        end
        samples=samples+1
    end
end
-- Equality, zero hysteresis, stationary samples after nil initialization,
-- accumulated sub-stud movement, teleport, Y axis, and heterogeneous modes.
for _,mode in ipairs({'full','lod1','lod2'}) do
    for _,h in ipairs({0,5,10}) do
        local positions={v(100,0,0),v(100,0,0),v(100,0,0),v(200,0,0),v(400,0,0),v(400,0,0)}
        for _,x in ipairs({100-h,100+h,200-h,200+h,400-h,400+h}) do
            for i=-10,10 do positions[#positions+1]=v(x+i*.1,0,0) end
        end
        for i=1,100 do positions[#positions+1]=v(0,0,i*.1) end
        positions[#positions+1]=v(10000,0,0); positions[#positions+1]=v(400-h,0,0)
        trace({record(1,v(0,0,0),mode,h),record(2,v(0,1,0),mode,h)},positions)
    end
end
math.randomseed(620)
local records, positions={},{}
for i=1,500 do records[i]=record(i,v(math.random(-600,600),math.random(-200,200),math.random(-600,600)),({'full','lod1','lod2'})[i%3+1],({0,5,10})[i%3+1]) end
for i=1,200 do positions[i]=v(i*.7,math.sin(i*.1)*40,i*.4) end
for i=201,250 do positions[i]=v(math.random(-2000,2000),math.random(-200,200),math.random(-2000,2000)) end
trace(records,positions)
local r=record(1,v(0,0,0),'lod2',10)
local start=resolves
for i=1,1000 do Cache.Resolve(r,v(40,0,0),observed,false) end
assert(resolves-start==1,'stationary policy work')
for i=1,50 do Cache.Resolve(r,v(40+i*.1,0,0),observed,false) end
assert(resolves-start==1,'safe movement did resolve')
Cache.Resolve(r,v(40,0,0),observed,true)
assert(resolves-start==2,'camera replacement not invalidated')
local queries=0
local c=Candidates.new({Query=function() queries=queries+1; return {r} end})
for i=1,100 do c:Retain(c:Collect(v(1,2,3))) end
assert(queries==1)
c:Collect(v(1,2,3),true); assert(queries==2)
-- A teleported-away retained record disappears from the cached list once
-- its unload succeeds; standing still must not retain the old region.
local remote=record(2,v(10000,0,0),'full',0)
local tele=Candidates.new(Index.new({r,remote}))
local initial=tele:Collect(v(0,0,0)); r.desired='FULL'; r.actual='FULL'; tele:Retain(initial)
local moved=tele:Collect(v(10000,0,0)); assert(#moved==2)
r.desired='UNLOADED'; r.actual='UNLOADED'; r.part=nil
tele:Retain(moved); assert(#tele:Collect(v(10000,0,0))==1)
-- One queue record, stationary no sort, replacement/cancel, exact priority
-- after motion, unload first, aging FIFO, and failed attempt gives up aging.
local sorts=0
local q=Queue.new(function(t) sorts=sorts+1; Candidates.SortTransitions(t) end)
local a,b=record(1,v(5,0,0),'full',0),record(2,v(10,0,0),'full',0)
a.desired='FULL'; b.desired='FULL'
local p1,p2={},{}
q:Begin(v(0,0,0)); q:Set(a,'FULL',p1); q:Set(b,'FULL',p1)
local o=q:Ordered(Cache.Distance); assert(o[1].record==a and #o==2)
local same=o[1]
for i=1,5 do q:Begin(v(0,0,0)); q:Set(a,'FULL',p1); q:Set(b,'FULL',p1); assert(q:Ordered(Cache.Distance)[1]==same) end
assert(sorts==1)
q:Begin(v(11,0,0)); assert(q:Ordered(Cache.Distance)[1].record==b)
q:Set(b,'FULL',p2); assert(q:Ordered(Cache.Distance)[1].prototype==p2)
q:Remove(b); assert(#q:Ordered(Cache.Distance)==1)
-- Aging within load class, then failure retry releases priority.
for i=1,8 do q:Begin(v(11,0,0)); q:Ordered(Cache.Distance) end
q:Set(b,'FULL',p1); o=q:Ordered(Cache.Distance); assert(o[1].record==a and o[1].aged)
q:Attempted(o[1]); assert(q:Ordered(Cache.Distance)[1].record==b)
a.actual='FULL'; a.desired='UNLOADED'; q:Set(a,'UNLOADED',nil)
assert(q:Ordered(Cache.Distance)[1].record==a)
q:Remove(a); q:Remove(b); assert(#q:Ordered(Cache.Distance)==0)
-- M621: same-variant prototype-generation refresh must enqueue a forced replacement.
local forced=record(3,v(8,0,0),'full',0)
forced.actual='FULL'; forced.desired='FULL'
q:Begin(v(11,0,0)); q:Set(forced,'FULL',p1,{},true)
o=q:Ordered(Cache.Distance); assert(#o==1 and o[1].record==forced and o[1].force)
q:Set(forced,'FULL',p1,{},false); assert(#q:Ordered(Cache.Distance)==0,'non-forced same actual must cancel')
print('M620/M621: '..comparisons..' desired comparisons, '..samples..' samples; stationary, threshold, queue and forced replacement lifecycle passed')
