local Segments=require(script.Parent:WaitForChild("MonsterRescueSegments"))
local function nearest(line,point)
    local best=nil
    for _,edge in ipairs(line.edges) do
        local p,t=Segments.Project(edge,point)
        local d=(p-point).Magnitude
        if not best or d<best.distance then
            best={name=line.name,line=line,edges=line.edges,edge=edge,point=p,t=t,distance=d,arc=edge.offset+t*edge.length}
        end
    end
    return best
end
local function rankRoutes(routes,goal)
    local ranked={}
    for _,line in pairs(routes) do table.insert(ranked,nearest(line,goal)) end
    table.sort(ranked,function(a,b)
        if a.distance~=b.distance then return a.distance<b.distance end
        return a.name<b.name
    end)
    return ranked
end
-- Visit each neighboring route at most once, closest transition first.
local function neighbors(line)
    local seen={[line]=true}
    local queue={line}
    local i=1
    return function()
        local current=queue[i]; i=i+1
        if not current then return nil end
        local nextLines={}
        for other,d in pairs(current.neighbors) do
            if not seen[other] then table.insert(nextLines,{line=other,distance=d}) end
        end
        table.sort(nextLines,function(a,b)
            if a.distance~=b.distance then return a.distance<b.distance end
            return a.line.name<b.line.name
        end)
        for _,item in ipairs(nextLines) do
            seen[item.line]=true; table.insert(queue,item.line)
        end
        return current
    end
end
return table.freeze({Rank=rankRoutes,Nearest=nearest,Neighbors=neighbors})
