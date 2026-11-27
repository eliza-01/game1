local Segments=require(script.Parent:WaitForChild("MonsterRescueSegments"))
local Routes=require(script.Parent:WaitForChild("MonsterRescueRoutes"))
local COARSE_STEP=20
local FINE_STEP=4
local EPS=1e-7
local function at(line,arc)
    local lo,hi=1,#line.edges
    while lo<hi do
        local mid=math.floor((lo+hi)/2)
        local edge=line.edges[mid]
        if arc>edge.offset+edge.length then lo=mid+1 else hi=mid end
    end
    local edge=line.edges[lo]
    return edge,math.clamp((arc-edge.offset)/edge.length,0,1)
end
-- A global arc-length grid centered on the monster projection. Clip the grid
-- analytically to the search sphere; long or folded routes do not oversample.
local function coarse(line,start,radius,origin,goalArc)
    local arcs,seen={},{}
    local function add(arc)
        local k=math.round(arc*1000000)
        if not seen[k] then seen[k]=true; table.insert(arcs,arc) end
    end
    add(origin); add(0); add(line.length)
    for _,edge in ipairs(line.edges) do
        local range=Segments.Interval(edge,start,radius)
        if range then
            local lo=edge.offset+range.lo*edge.length
            local hi=edge.offset+range.hi*edge.length
            for i=math.ceil((lo-origin-EPS)/COARSE_STEP),math.floor((hi-origin+EPS)/COARSE_STEP) do
                add(math.clamp(origin+i*COARSE_STEP,0,line.length))
            end
        end
    end
    table.sort(arcs,function(a,b)
        local da,db=math.abs(a-origin),math.abs(b-origin)
        if math.abs(da-db)>EPS then return da<db end
        local ga,gb=math.abs(a-goalArc),math.abs(b-goalArc)
        if ga~=gb then return ga<gb end
        return a<b
    end)
    return arcs
end
local function find(ctx,line,try)
    local origin=Routes.Nearest(line,ctx.start)
    local goal=Routes.Nearest(line,ctx.goal)
    local function candidate(arc)
        local edge,t=at(line,arc)
        local range=Segments.Interval(edge,ctx.start,ctx.radius)
        if not range or t<range.lo-EPS or t>range.hi+EPS then return nil end
        return Segments.Candidate(edge,ctx.start,range,t,ctx.allowed,ctx.observe,"GRAPH_ENTRY")
    end
    for _,arc in ipairs(coarse(line,ctx.start,ctx.radius,origin.arc,goal.arc)) do
        local entry=candidate(arc)
        if entry and try(entry) then
            if math.abs(arc-origin.arc)<=EPS then return entry end
            local best=entry
            local limit=math.min(COARSE_STEP,math.abs(goal.arc-arc))
            local refined=0
            local direction=goal.arc>=arc and 1 or -1
            -- Refine toward the goal projection until a blocked point or the
            -- projection itself. Never leave the entry search sphere.
            while refined<limit-EPS do
                local step=math.min(FINE_STEP,limit-refined)
                arc=arc+direction*step
                refined=refined+step
                local nextEntry=candidate(arc)
                if not nextEntry or not try(nextEntry) then break end
                best=nextEntry
            end
            return best
        end
    end
    return nil
end
return table.freeze({Find=find})
