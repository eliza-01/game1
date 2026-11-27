local Segments=require(script.Parent:WaitForChild("MonsterRescueSegments"))
local Queries=require(script.Parent:WaitForChild("MonsterRescueQueries"))
local Paths=require(script.Parent:WaitForChild("MonsterRescuePaths"))
local key,interval,alternatives,exitLess=Segments.Key,Segments.Interval,Segments.ExitCandidates,Segments.ExitLess
local function find(ctx,route,entriesByEdge,distances)
    local goal,allowed,observe,stats,maxExitDistance=ctx.goal,ctx.allowed,ctx.observe,ctx.stats,ctx.exitLimit
    -- Exit priority: height, target distance, then entry distance/path cost
    -- at equal exit rank. Only reachable segments are considered.
    local best,bestExit=nil,nil
    local exitSeen={}
    local reachable={}
    for _,edge in ipairs(route.edges) do
        local connected=entriesByEdge[edge] or distances[edge.a] or distances[edge.b]
        if connected then
            local range=interval(edge,goal,maxExitDistance)
            if range then
                table.insert(reachable,{edge=edge,range=range})
            elseif observe then
                local p=Segments.Project(edge,goal)
                observe("GRAPH_EXIT_EDGE",edge,p,(p-goal).Magnitude,"ExitDistance")
            end
        elseif observe then
            local range=interval(edge,goal,maxExitDistance)
            if range then
                local p=edge.a.position+range.delta*range.nearest
                observe("GRAPH_EXIT_EDGE",edge,p,(p-goal).Magnitude,"Unreachable")
            end
        end
    end
    local function searchExits(sampleInterior)
        local found={}
        for _,item in ipairs(reachable) do
            for _,exit in ipairs(alternatives(item.edge,goal,item.range,allowed,sampleInterior,observe)) do
                table.insert(found,exit)
            end
        end
        table.sort(found,exitLess)
        for _,exit in ipairs(found) do
            if bestExit and exitLess(bestExit,exit) then break end
            local edge=exit.edge
            local k=key(exit.point)
            local seen=exitSeen[edge] or {}
            exitSeen[edge]=seen
            if not seen[k] then
                seen[k]=true
                local plan=Paths.ToExit(exit,entriesByEdge,distances)
                if plan then
                    stats.reachableExits=stats.reachableExits+1
                    if Queries.Check(ctx,"exit",exit) and (not bestExit or exitLess(exit,bestExit) or Paths.Less(plan,best)) then
                        best,bestExit=plan,exit
                    end
                end
            end
        end
    end
    searchExits(false)
    -- A blocked analytical exit need not invalidate a whole segment. As a
    -- bounded last resort try other interior points, without recasting them.
    if not best then searchExits(true) end
    return best,bestExit
end

return table.freeze({Find=find})
