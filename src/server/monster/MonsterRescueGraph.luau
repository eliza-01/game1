local Config=require(script.Parent:WaitForChild("MonsterNavigationConfig"))
local Topology=require(script.Parent:WaitForChild("MonsterRescueTopology"))
local Routes=require(script.Parent:WaitForChild("MonsterRescueRoutes"))
local Queries=require(script.Parent:WaitForChild("MonsterRescueQueries"))
local Entries=require(script.Parent:WaitForChild("MonsterRescueEntries"))
local Paths=require(script.Parent:WaitForChild("MonsterRescuePaths"))
local Exits=require(script.Parent:WaitForChild("MonsterRescueExits"))
local Workspace=game:GetService("Workspace")
local Graph={}
local routesByName
function Graph.Initialize()
    if not routesByName then routesByName=Topology.Build(Workspace:FindFirstChild("Game1RescueRoutes"),Config.routeConnectionHeight) end
end
local function attempt(ctx,route,line)
    local entries=Entries.Find(ctx,line)
    if not entries then
        if ctx.observe then Exits.Find(ctx,route,{}, {}) end
        return nil
    end
    local distances=ctx.pathResults[line]
    if not distances then
        distances=Paths.Search(ctx,entries)
        ctx.pathResults[line]=distances
    end
    local best,exit=Exits.Find(ctx,route,entries,distances)
    if not best then return nil end
    if ctx.observe then
        ctx.observe("GRAPH_SELECTED_ENTRY",best.entry.edge,best.entry.point,best.entry.distance,"Selected")
        ctx.observe("GRAPH_SELECTED_EXIT",exit.edge,exit.point,exit.distance,"Selected")
    end
    return {points=Paths.Reconstruct(best,exit),cost=best.cost,
        exitHeightDelta=exit.heightDelta,exitDistance=exit.distance,routeId=route.name,entryRouteId=line.name}
end
function Graph.Find(start,goal,canConnect,allowed,canExit,observe,canTransfer)
    Graph.Initialize()
    local ctx=Queries.New(start,goal,Config.searchDistance,canConnect,allowed,canExit,observe,canTransfer)
    for _,route in ipairs(Routes.Rank(routesByName,goal)) do
        if route.distance>ctx.exitLimit+1e-8 then
            if observe then observe("GRAPH_ROUTE",route.edge,route.point,route.distance,"ExitDistance") end
        else
            if observe then observe("GRAPH_ROUTE",route.edge,route.point,route.distance,"TargetRank") end
            for line in Routes.Neighbors(route.line) do
                if observe and line~=route.line then
                    local p=Routes.Nearest(line,start)
                    observe("GRAPH_ROUTE",p.edge,p.point,p.distance,"ConnectedFallback")
                end
                local plan=attempt(ctx,route,line)
                if plan then return plan,ctx.stats end
            end
        end
    end
    return nil,ctx.stats
end
return table.freeze(Graph)
