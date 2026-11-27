local EXIT_SAMPLE_STEP=4
local function key(p)
    return string.format("%d:%d:%d", math.round(p.X*100), math.round(p.Y*100), math.round(p.Z*100))
end
local function project(edge,point)
    local delta=edge.b.position-edge.a.position
    local t=math.clamp((point-edge.a.position):Dot(delta)/(edge.length*edge.length),0,1)
    return edge.a.position+delta*t,t
end
-- Among exits no farther from the target than the search origin,
-- priority is lexicographic: height relative to target feet, then distance.
-- A very small numerical tolerance is used only for ranking equivalent heights.
local function exitLess(a,b)
    if a.heightRank~=b.heightRank then return a.heightRank<b.heightRank end
    if a.distance~=b.distance then return a.distance<b.distance end
    return false
end
-- All candidate coordinates are computed on a finite 3D segment, clipped to
-- the search/progress sphere. Authored vertices have no special selection rank.
local function interval(edge,point,radius)
    local delta=edge.b.position-edge.a.position
    local offset=point-edge.a.position
    local projection=offset:Dot(delta)/(edge.length*edge.length)
    local perpendicular=offset-delta*projection
    local remaining=radius*radius-perpendicular:Dot(perpendicular)
    if remaining < -1e-8 then return nil end
    local span=math.sqrt(math.max(0,remaining))/edge.length
    local lo,hi=math.max(0,projection-span),math.min(1,projection+span)
    if lo>hi then return nil end
    local nearest=math.clamp(projection,lo,hi)
    local height=nearest
    if math.abs(delta.Y)>1e-6 then height=math.clamp(offset.Y/delta.Y,lo,hi) end
    return {lo=lo,hi=hi,nearest=nearest,height=height,delta=delta}
end
local function candidate(edge,point,range,t,allowed,observe,stage)
    local p=edge.a.position+range.delta*t
    local ok,reason=allowed(p)
    if not ok then
        if observe then observe(stage,edge,p,(p-point).Magnitude,reason or "Policy") end
        return nil
    end
    local heightDelta=math.abs(p.Y-point.Y)
    return {edge=edge,point=p,t=t,distance=(p-point).Magnitude,heightDelta=heightDelta,heightRank=math.round(heightDelta*10000)}
end
local function exitCandidates(edge,point,range,allowed,sampleInterior,observe)
    local found,seen={},{}
    local function add(t)
        local c=candidate(edge,point,range,t,allowed,observe,"GRAPH_EXIT")
        if c then
            local k=key(c.point)
            if not seen[k] then seen[k]=true; table.insert(found,c) end
        end
    end
    add(range.height); add(range.nearest); add(range.lo); add(range.hi)
    if sampleInterior then
        -- Cap the fallback grid; normal analytical exits need no grid.
        local steps=math.max(1,math.ceil((range.hi-range.lo)*edge.length/EXIT_SAMPLE_STEP))
        steps=math.min(32,steps)
        for i=0,steps do add(range.lo+(range.hi-range.lo)*i/steps) end
    end
    table.sort(found,exitLess)
    return found
end


return table.freeze({Key=key,Project=project,Interval=interval,Candidate=candidate,ExitCandidates=exitCandidates,ExitLess=exitLess})
