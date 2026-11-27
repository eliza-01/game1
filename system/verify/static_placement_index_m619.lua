-- Run the production index and candidate lifecycle with the unchanged Location
-- distance policy. Lua 5.3 adaptation is limited to Luau compound assignment;
-- the following house/visual methods are deliberately not part of this test.
local Index = dofile('src/client/world/StaticPlacementIndex.luau')
local Candidates = dofile('src/client/world/LocationLodCandidates.luau')
local file = assert(io.open('src/shared/world/LocationLodDistancePolicy.luau'))
local source = file:read('*a'); file:close()
source = assert(source:match('^(.-)%-%- Distance to the rotated visual bounds'))
source = source:gsub('index %+= 1', 'index = index + 1'):gsub('index %-=%s*1', 'index = index - 1')
table.freeze = table.freeze or function(t) return t end
local Policy = assert(load(source .. '\nreturn Policy'))()
local function v(x,y,z) return {X=x,Y=y,Z=z} end
local function distance(a,b) return math.sqrt((a.X-b.X)^2+(a.Y-b.Y)^2+(a.Z-b.Z)^2) end
local function record(order, x,y,z, mode, hide, h)
    return {order=order,pivot=v(x,y,z),mode=mode,distances={lod1=math.floor(hide/4),lod2=math.floor(hide/2),hide=hide,hysteresis=h},actual='UNLOADED'}
end
local queries, comparisons = 0,0
local function scenario(records, positions, budget)
    local index = Index.new(records)
    local candidates = Candidates.new(index)
    local reference, referenceActual = {}, {}
    for tick, camera in ipairs(positions) do
        local localRecords = candidates:Collect(camera)
        local seen, transitions = {}, {}
        for _, r in ipairs(localRecords) do
            assert(not seen[r], 'duplicate candidate'); seen[r]=true
            r.distance = distance(camera,r.pivot)
            r.desired = Policy.Resolve(r.distance,r.desired,r.distances,r.mode)
            -- Simulate missing preferred templates and deferred commits; a
            -- record with desired but no actual must still survive teleport.
            local variant = r.desired
            if tick%7==1 and r.order%3==0 and variant~='UNLOADED' then variant=r.actual end
            if variant~=r.actual then transitions[#transitions+1]={record=r,variant=variant} end
        end
        -- Full-scan oracle: existing unload-first/nearest priority, plus
        -- manifest ordinal for the previously unspecified tie case.
        local expected = {}
        for _,r in ipairs(records) do
            reference[r]=Policy.Resolve(distance(camera,r.pivot),reference[r],r.distances,r.mode)
            local actual=referenceActual[r] or 'UNLOADED'
            local variant=reference[r]
            if tick%7==1 and r.order%3==0 and variant~='UNLOADED' then variant=actual end
            if variant~=actual then
                expected[#expected+1]={record=r,variant=variant,unload=reference[r]=='UNLOADED' and actual~='UNLOADED',distance=distance(camera,r.pivot)}
            end
        end
        table.sort(expected,function(a,b)
            if a.unload~=b.unload then return a.unload end
            if a.distance~=b.distance then return a.distance<b.distance end
            return a.record.order<b.record.order
        end)
        Candidates.SortTransitions(transitions)
        assert(#transitions==#expected, 'transition count differs')
        for i,t in ipairs(transitions) do
            assert(t.record==expected[i].record and t.variant==expected[i].variant,'transition ordering differs')
            if i<=budget then
                t.record.actual=t.variant
                referenceActual[t.record]=expected[i].variant
                t.record.part=t.variant~='UNLOADED' and {} or nil
            end
        end
        candidates:Retain(localRecords)
        for _,r in ipairs(records) do
            assert(r.actual==(referenceActual[r] or 'UNLOADED'), 'actual mismatch')
            assert((r.desired or 'UNLOADED')==reference[r], 'desired mismatch at tick '..tick..', record '..r.order)
            if reference[r]~='UNLOADED' or r.actual~='UNLOADED' then assert(seen[r], 'lost live record') end
            comparisons=comparisons+1
        end
        queries=queries+1
    end
    return candidates
end
-- Exact thresholds, nil versus prior UNLOADED, negative coordinates, Y,
-- large radius, a blocked-budget unload, teleport back and repeated samples.
for _, mode in ipairs({'full','lod1','lod2'}) do
    for _, h in ipairs({0,10}) do
        local records={record(1,0,0,0,mode,400,h),record(2,-10000,500,0,mode,10000,h),record(3,0,0,10000,mode,400,h)}
        scenario(records,{v(0,0,0),v(99,0,0),v(100,0,0),v(100+h,0,0),v(200+h,0,0),v(400+h,0,0),v(400-h,0,0),v(400-h+1,0,0),v(400-h,0,0),v(0,400+h,0),v(0,400-h,0),v(0,0,10000),v(-1000000,500,0),v(-1000000,500,0),v(400-h+1,0,0),v(400-h,0,0)},1)
        -- A previously unobserved record must enter with previous UNLOADED,
        -- rather than nil, in the inner half of the hide hysteresis band.
        scenario({record(1,0,0,0,mode,400,h)},{v(10000,0,0),v(400-h+1,0,0),v(400-h,0,0),v(0,0,0)},0)
    end
end
-- Reproducible sparse/dense worlds with heterogeneous ranges.
math.randomseed(619)
for _, n in ipairs({0,1,500,2000,10000}) do
    local records, positions = {}, {}
    for i=1,n do
        local hide=({160,400,1000,10000})[i%4+1]
        local h=({0,5,10})[i%3+1]
        local mode=({'full','lod1','lod2'})[i%3+1]
        records[i]=record(i,math.random(-50000,50000),math.random(-4000,4000),math.random(-50000,50000),mode,hide,h)
    end
    for i=1,60 do
        if n>0 and i%3==0 then positions[i]=records[(i*31)%n+1].pivot
        else positions[i]=v(math.random(-50000,50000),math.random(-5000,5000),math.random(-50000,50000)) end
    end
    scenario(records,positions,8)
end
-- Sparse world must not enumerate global bounds, or return distant points.
local sparse={record(1,-1000000,0,0,'full',400,10),record(2,1000000,0,0,'full',10000,10)}
local index=Index.new(sparse)
assert(#index:Query(v(0,0,0))==0)
assert(#index:Query(v(1000000,0,10010))==1)
-- Unload before loads; equal distances use a fixed manifest ordinal.
local function t(order,d,desired,actual) return {record={order=order,distance=d,desired=desired,actual=actual}} end
local a,b,c,d=t(3,1,'FULL','UNLOADED'),t(2,5,'FULL','UNLOADED'),t(1,5,'FULL','LOD1'),t(4,100,'UNLOADED','FULL')
local sorted={a,b,c,d}; Candidates.SortTransitions(sorted)
assert(sorted[1]==d and sorted[2]==a and sorted[3]==c and sorted[4]==b)
print('M619: '..queries..' camera samples; '..comparisons..' desired-state comparisons passed')
