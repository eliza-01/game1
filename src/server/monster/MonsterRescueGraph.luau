local Config=require(script.Parent:WaitForChild("MonsterNavigationConfig"))
-- Read-only authored navigation graph. Coordinates are ground/foot positions.
-- Only explicit coincident vertices connect; crossing lines on different floors do not.
local Workspace = game:GetService("Workspace")
local Graph = {}
local nodes, edges = {}, {}
local loaded = false
local MAX_EDGES = 2048

local function key(p)
    return string.format("%d:%d:%d", math.round(p.X*100), math.round(p.Y*100), math.round(p.Z*100))
end
local function load()
    if loaded then return end
    loaded = true
    local folder = Workspace:FindFirstChild("Game1RescueRoutes")
    if not folder then return end
    local byKey = {}
    local function node(p)
        local k = key(p)
        if not byKey[k] then
            local n = {position=p, links={}}
            byKey[k] = n; table.insert(nodes,n)
        end
        return byKey[k]
    end
    local routes = folder:GetChildren()
    table.sort(routes,function(a,b) return a.Name<b.Name end)
    for _, route in ipairs(routes) do
        if route:IsA("Folder") then
            local points = {}
            for _, value in ipairs(route:GetChildren()) do
                if value:IsA("Vector3Value") and tonumber(value.Name) then table.insert(points,value) end
            end
            table.sort(points,function(a,b) return tonumber(a.Name)<tonumber(b.Name) end)
            for i=2,#points do
                if #edges>=MAX_EDGES then warn("[game1] Rescue route edge limit reached"); return end
                local a,b = node(points[i-1].Value),node(points[i].Value)
                local length = (b.position-a.position).Magnitude
                if length>=0.01 then
                    local edge={a=a,b=b,length=length}
                    table.insert(edges,edge)
                    table.insert(a.links,{node=b,length=length}); table.insert(b.links,{node=a,length=length})
                end
            end
        end
    end
end

-- Exit priority is lexicographic: height relative to target feet, then distance.
-- A very small numerical tolerance is used only for ranking equivalent heights.
local function exitLess(a,b)
    if a.heightRank~=b.heightRank then return a.heightRank<b.heightRank end
    if a.distance~=b.distance then return a.distance<b.distance end
    return false
end
-- Try the interior projection and endpoints. A blocked projection is not
-- evidence that the entire authored edge is inaccessible.
local function candidates(point, radius, height, allowed, isExit)
    local found={}
    for _,edge in ipairs(edges) do
        local delta=edge.b.position-edge.a.position
        local t=math.clamp((point-edge.a.position):Dot(delta)/(edge.length*edge.length),0,1)
        if isExit and math.abs(delta.Y)>1e-6 then
            t=math.clamp((point.Y-edge.a.position.Y)/delta.Y,0,1)
        end
        local function add(u)
            local p=edge.a.position+delta*u
            local d=(p-point).Magnitude
            local heightDelta=math.abs(p.Y-point.Y)
            if (not radius or d<=radius+1e-6) and (not height or heightDelta<=height) and allowed(p) then
                table.insert(found,{edge=edge,point=p,t=u,distance=d,heightDelta=heightDelta,heightRank=math.round(heightDelta*10000)})
            end
        end
        add(t)
        if t>1e-6 then add(0) end
        if t<1-1e-6 then add(1) end
    end
    table.sort(found,function(a,b)
        if isExit then return exitLess(a,b) end
        return a.distance<b.distance
    end)
    return found
end

local function push(heap,entry)
    local i=#heap+1
    while i>1 do
        local parent=math.floor(i/2)
        if heap[parent].cost<=entry.cost then break end
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
        if child<#heap and heap[child+1].cost<heap[child].cost then child=child+1 end
        if last.cost<=heap[child].cost then break end
        heap[i]=heap[child]; i=child
    end
    heap[i]=last
    return first
end

-- Multi-source shortest path including projected entry/exit on edge interiors.
-- Length is full 3D arc length, not distance to the nearest vertex.
function Graph.Find(start, goal, canConnect, allowed, canExit)
    allowed=allowed or function() return true end
    canExit=canExit or canConnect
    load()
    local stats={entryCandidates=0,entries=0,entryChecks=0,reachableExits=0,exitChecks=0}
    if #edges==0 then return nil,stats end
    local entriesByEdge, entryResults = {},{}
    local distances, previous, source, visited, heap = {},{},{},{},{}
    -- Radius and height apply only to joining the graph. No rejected entry
    -- consumes an arbitrary top-eight budget. Shared vertex queries are cached.
    local entries=candidates(start,Config.searchDistance,2,allowed,false)
    stats.entryCandidates=#entries
    for _,entry in ipairs(entries) do
        local k=key(entry.point)
        if entryResults[k]==nil then
            entryResults[k]=canConnect(start,entry.point)==true
            stats.entryChecks=stats.entryChecks+1
        end
        if entryResults[k] then
            stats.entries=stats.entries+1
            local list=entriesByEdge[entry.edge] or {}
            entriesByEdge[entry.edge]=list; table.insert(list,entry)
            for _,endpoint in ipairs({entry.edge.a,entry.edge.b}) do
                local d=entry.distance+(entry.point-endpoint.position).Magnitude
                if allowed(endpoint.position) and d<(distances[endpoint] or math.huge) then
                    distances[endpoint]=d; source[endpoint]=entry; push(heap,{node=endpoint,cost=d})
                end
            end
        end
    end
    if stats.entries==0 then return nil,stats end
    -- First find reachable nodes; disconnected routes never consume exit casts.
    while #heap>0 do
        local item=pop(heap)
        local current,cost=item.node,item.cost
        if not visited[current] and cost==distances[current] then
            visited[current]=true
            for _,link in ipairs(current.links) do
                local d=cost+link.length
                if allowed(link.node.position) and d<(distances[link.node] or math.huge) then
                    distances[link.node]=d; previous[link.node]=current; source[link.node]=source[current]
                    push(heap,{node=link.node,cost=d})
                end
            end
        end
    end
    -- Search the entire reachable graph for the exit, in height/distance order.
    -- Only cast until a reachable valid rank wins; ties use total path cost.
    local best,bestCost,bestExit=nil,math.huge,nil
    local exitResults={}
    for _,exit in ipairs(candidates(goal,nil,nil,allowed,true)) do
        if bestExit and exitLess(bestExit,exit) then break end
        local edge=exit.edge
        local cost,endpoint,direct=math.huge,nil,nil
        for _,entry in ipairs(entriesByEdge[edge] or {}) do
            local d=entry.distance+math.abs(entry.t-exit.t)*edge.length+exit.distance
            if d<cost then cost=d; direct=entry end
        end
        for _,n in ipairs({edge.a,edge.b}) do
            if distances[n] then
                local d=distances[n]+(exit.point-n.position).Magnitude+exit.distance
                if d<cost then cost=d; endpoint=n; direct=nil end
            end
        end
        if cost<math.huge then
            stats.reachableExits=stats.reachableExits+1
            local k=key(exit.point)
            if exitResults[k]==nil then
                exitResults[k]=canExit(exit.point,goal)==true
                stats.exitChecks=stats.exitChecks+1
            end
            if exitResults[k] and (not bestExit or exitLess(exit,bestExit) or cost<bestCost) then
                local path={exit.point}
                if direct then
                    table.insert(path,1,direct.point)
                else
                    local n=endpoint
                    while n do table.insert(path,1,n.position); n=previous[n] end
                    table.insert(path,1,source[endpoint].point)
                end
                best,bestCost,bestExit=path,cost,exit
            end
        end
    end
    if best then return {points=best,cost=bestCost,exitHeightDelta=bestExit.heightDelta,exitDistance=bestExit.distance},stats end
    return nil,stats
end
return table.freeze(Graph)
