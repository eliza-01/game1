local Queries=require(script.Parent:WaitForChild("MonsterRescueQueries"))
-- For a given reachable exit, prefer the closest accessible entry before
-- comparing arc length. Otherwise a distant vertex can win by cutting off
-- part of the authored route, even with a clear perpendicular entry.
local function pathLess(a,b)
    if not b then return true end
    if a.entry.distance~=b.entry.distance then return a.entry.distance<b.entry.distance end
    return a.cost<b.cost
end
local function push(heap,entry)
    local i=#heap+1
    while i>1 do
        local parent=math.floor(i/2)
        if not pathLess(entry,heap[parent]) then break end
        heap[i]=heap[parent]; i=parent
    end
    heap[i]=entry
end
local function pop(heap)
    local first=heap[1]
    local last=table.remove(heap)
    if #heap==0 then return first end
    local i=1
    while i*2<=#heap do
        local child=i*2
        if child<#heap and pathLess(heap[child+1],heap[child]) then child=child+1 end
        if not pathLess(heap[child],last) then break end
        heap[i]=heap[child]; i=child
    end
    heap[i]=last
    return first
end

local function search(ctx,entriesByEdge)
    local start,allowed,observe=ctx.start,ctx.allowed,ctx.observe
    local distances,visited,heap={},{},{}
    local entries={}
    for _,entry in pairs(entriesByEdge) do table.insert(entries,entry) end
    table.sort(entries,function(a,b) return a.edge.id<b.edge.id end)
    for _,entry in ipairs(entries) do
        for _,endpoint in ipairs({entry.edge.a,entry.edge.b}) do
            local d=entry.distance+(entry.point-endpoint.position).Magnitude
            local item={node=endpoint,cost=d,entry=entry}
            local ok,reason=allowed(endpoint.position)
            if ok and pathLess(item,distances[endpoint]) then
                distances[endpoint]=item; push(heap,item)
            elseif not ok and observe then
                observe("GRAPH_NODE",entry.edge,endpoint.position,(endpoint.position-start).Magnitude,reason or "Policy")
            end
        end
    end
    -- Multi-source Dijkstra, lexicographic (entry distance, full arc length).
    -- Keep immutable predecessor records so reconstruction follows the source
    -- that actually won rather than a stale predecessor from another entry.
    while #heap>0 do
        local item=pop(heap)
        local current=item.node
        if not visited[current] and item==distances[current] then
            visited[current]=true
            for _,link in ipairs(current.links) do
                local nextItem={node=link.node,cost=item.cost+link.length,entry=item.entry,previous=item}
                local ok,reason=allowed(link.node.position)
                if ok and pathLess(nextItem,distances[link.node]) and Queries.Transfer(ctx,link.edge) then
                    distances[link.node]=nextItem; push(heap,nextItem)
                elseif not ok and observe then
                    observe("GRAPH_NODE",link.edge,link.node.position,(link.node.position-start).Magnitude,reason or "Policy")
                end
            end
        end
    end
    return distances
end
local function toExit(exit,entriesByEdge,distances)
    local edge=exit.edge
    local plan=nil
    local entry=entriesByEdge[edge]
    if entry then
        plan={entry=entry,cost=entry.distance+math.abs(entry.t-exit.t)*edge.length+exit.distance}
    end
    for _,n in ipairs({edge.a,edge.b}) do
        local record=distances[n]
        if record then
            local option={entry=record.entry,cost=record.cost+(exit.point-n.position).Magnitude+exit.distance,record=record}
            if pathLess(option,plan) then plan=option end
        end
    end
    return plan
end
local function reconstruct(best,exit)
    local reverse={exit.point}
    local record=best.record
    while record do table.insert(reverse,record.node.position); record=record.previous end
    table.insert(reverse,best.entry.point)
    local path={}
    for i=#reverse,1,-1 do table.insert(path,reverse[i]) end
    return path
end

return table.freeze({Search=search,ToExit=toExit,Less=pathLess,Reconstruct=reconstruct})
