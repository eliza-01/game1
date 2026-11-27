local Segments=require(script.Parent:WaitForChild("MonsterRescueSegments"))
local Connections=require(script.Parent:WaitForChild("MonsterRescueConnections"))
local MAX_EDGES=2048

local function build(folder,maxHeightDelta)
    local routes,raw={},{}
    if not folder then return routes end
    local function node(p) return {position=p,links={}} end
    local folders=folder:GetChildren()
    table.sort(folders,function(a,b) return a.Name<b.Name end)
    for _,route in ipairs(folders) do
        if route:IsA("Folder") then
            local points={}
            for _,value in ipairs(route:GetChildren()) do
                if value:IsA("Vector3Value") and tonumber(value.Name) then table.insert(points,value) end
            end
            table.sort(points,function(a,b) return tonumber(a.Name)<tonumber(b.Name) end)
            local byKey={}
            local function routeNode(p)
                local k=Segments.Key(p)
                if not byKey[k] then byKey[k]=node(p) end
                return byKey[k]
            end
            local previous=points[1] and routeNode(points[1].Value)
            local line={edges={},neighbors={},length=0,name=route.Name}
            for i=2,#points do
                if #raw>=MAX_EDGES then break end
                local p=points[i].Value
                local length=(p-previous.position).Magnitude
                if length>=.01 then
                    local nextNode=routeNode(p)
                    local segment={a=previous,b=nextNode,length=length,route=line,
                        source=route.Name..":"..points[i-1].Name.."-"..points[i].Name}
                    segment.cuts={{node=previous,t=0},{node=nextNode,t=1}}
                    table.insert(raw,segment); previous=nextNode
                    routes[route.Name]=line
                end
            end
        end
        if #raw>=MAX_EDGES then warn("[game1] Rescue route authored edge limit reached"); break end
    end
    local id=0
    local function link(a,b,source,route,connector)
        id=id+1
        local edge={a=a,b=b,length=(b.position-a.position).Magnitude,sources={[source]=true},routes={},id=id,connector=connector}
        if route then
            edge.routes[route.name]=true; edge.offset=route.length
            route.length=route.length+edge.length; table.insert(route.edges,edge)
        end
        table.insert(a.links,{node=b,length=edge.length,edge=edge})
        table.insert(b.links,{node=a,length=edge.length,edge=edge})
        return edge
    end
    local function cut(segment,t)
        for _,c in ipairs(segment.cuts) do
            if math.abs(c.t-t)*segment.length<1e-6 then return c.node end
        end
        local n=node(segment.a.position+(segment.b.position-segment.a.position)*t)
        table.insert(segment.cuts,{node=n,t=t}); return n
    end
    Connections.Build(raw,cut,link,maxHeightDelta)
    for _,segment in ipairs(raw) do
        table.sort(segment.cuts,function(a,b) return a.t<b.t end)
        for i=2,#segment.cuts do link(segment.cuts[i-1].node,segment.cuts[i].node,segment.source,segment.route,false) end
    end
    return routes
end
return table.freeze({Build=build})
