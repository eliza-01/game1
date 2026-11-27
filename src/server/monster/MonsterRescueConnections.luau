local Segments=require(script.Parent:WaitForChild("MonsterRescueSegments"))
local CONTACT_EPSILON=1e-6

-- Only the first and last nodes of a polyline can originate a transfer.
-- Interior nodes can receive a transfer but never generate one.
local function endpoints(raw)
    local ordered,byRoute={},{}
    for _,segment in ipairs(raw) do
        local line=byRoute[segment.route]
        if not line then
            line={first=segment,last=segment}
            byRoute[segment.route]=line; table.insert(ordered,line)
        end
        line.last=segment
    end
    local result={}
    for _,line in ipairs(ordered) do
        local a,b=line.first.a,line.last.b
        local closed=a==b or (a.position-b.position).Magnitude<=CONTACT_EPSILON
        table.insert(result,{node=a,segment=line.first,closed=closed})
        if not closed then table.insert(result,{node=b,segment=line.last}) end
    end
    return result
end

-- Nearest point within the vertical slab, not merely the nearest vertex or
-- the unrestricted projection (which might lie outside the allowed height).
local function projectWithinHeight(segment,position,maxHeightDelta)
    local a,b=segment.a.position,segment.b.position
    local dy=b.Y-a.Y
    local lo,hi=0,1
    if math.abs(dy)<=CONTACT_EPSILON then
        if math.abs(a.Y-position.Y)>maxHeightDelta then return nil end
    else
        local t1=(position.Y-maxHeightDelta-a.Y)/dy
        local t2=(position.Y+maxHeightDelta-a.Y)/dy
        lo,hi=math.max(0,math.min(t1,t2)),math.min(1,math.max(t1,t2))
        if lo>hi then return nil end
    end
    local _,t=Segments.Project(segment,position)
    t=math.clamp(t,lo,hi)
    local p=a+(b-a)*t
    return t,(p-position).Magnitude
end

local function build(raw,cut,link,maxHeightDelta)
    local linked,proposals={},{}
    local function connect(endpoint,other,t,distance)
        local node,dest=endpoint.node,cut(other,t)
        if linked[node] and linked[node][dest] then return end
        linked[node]=linked[node] or {}; linked[dest]=linked[dest] or {}
        linked[node][dest]=true; linked[dest][node]=true
        link(node,dest,endpoint.segment.source.."~"..other.source,nil,true)
        local a,b=endpoint.segment.route,other.route
        local old=a.neighbors[b]
        if not old or distance<old then a.neighbors[b]=distance; b.neighbors[a]=distance end
    end
    -- Resolve existing endpoint contacts before proposing nonzero bridges.
    for index,endpoint in ipairs(endpoints(raw)) do
        local best,bestT,bestDistance=nil,nil,math.huge
        for _,other in ipairs(raw) do
            if other.route~=endpoint.segment.route then
                local t,distance=projectWithinHeight(other,endpoint.node.position,maxHeightDelta)
                if t then
                    if distance<=CONTACT_EPSILON then
                        connect(endpoint,other,t,distance)
                    elseif distance<bestDistance then
                        best,bestT,bestDistance=other,t,distance
                    end
                end
            end
        end
        if best and not endpoint.closed then
            table.insert(proposals,{endpoint=endpoint,other=best,t=bestT,distance=bestDistance,index=index})
        end
    end
    -- Shortest bridges first; a terminal already connected by an incoming
    -- bridge does not need to originate another one. Stable ties by route order.
    table.sort(proposals,function(a,b)
        if a.distance~=b.distance then return a.distance<b.distance end
        return a.index<b.index
    end)
    for _,p in ipairs(proposals) do
        if not linked[p.endpoint.node] then connect(p.endpoint,p.other,p.t,p.distance) end
    end
end
return table.freeze({Build=build})
