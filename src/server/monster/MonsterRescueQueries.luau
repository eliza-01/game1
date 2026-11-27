local Segments=require(script.Parent:WaitForChild("MonsterRescueSegments"))

local Queries={}
function Queries.New(start,goal,radius,canConnect,allowed,canExit,observe,canTransfer)
    return {
        start=start,goal=goal,radius=radius,exitLimit=(start-goal).Magnitude,
        allowed=allowed or function() return true end,observe=observe,
        entryPlans={},pathResults={},transferResults={},canTransfer=canTransfer,
        entry={callback=canConnect,results={},details=observe and {},counter="entryChecks",stage="GRAPH_ENTRY"},
        exit={callback=canExit or canConnect,results={},details=observe and {},counter="exitChecks",stage="GRAPH_EXIT"},
        stats={entryCandidates=0,entries=0,entryChecks=0,reachableExits=0,exitChecks=0,transferChecks=0},
    }
end
function Queries.Check(ctx,kind,candidate)
    local channel=ctx[kind]
    local k=Segments.Key(candidate.point)
    local cached=channel.results[k]~=nil
    if not cached then
        local a,b=ctx.start,candidate.point
        if kind=="exit" then a,b=candidate.point,ctx.goal end
        local ok,reason,hit=channel.callback(a,b)
        channel.results[k]=ok==true
        if ctx.observe then channel.details[k]={reason=reason,hit=hit} end
        ctx.stats[channel.counter]=ctx.stats[channel.counter]+1
    end
    local accepted=channel.results[k]
    if ctx.observe then
        local detail=channel.details[k]
        ctx.observe(channel.stage,candidate.edge,candidate.point,candidate.distance,
            accepted and "Accepted" or detail.reason or "Blocked",detail.hit,cached)
    end
    return accepted
end
function Queries.Transfer(ctx,edge)
    if not edge.connector or edge.length<1e-6 then return true end
    if ctx.transferResults[edge]==nil then
        local ok,reason,hit=false,"TransferUnchecked",nil
        if ctx.canTransfer then
            ok,reason,hit=ctx.canTransfer(edge.a.position,edge.b.position)
            ctx.stats.transferChecks=ctx.stats.transferChecks+1
        end
        ctx.transferResults[edge]=ok==true
        if ctx.observe then ctx.observe("GRAPH_TRANSFER",edge,edge.b.position,edge.length,ok and "Accepted" or reason or "Blocked",hit) end
    end
    return ctx.transferResults[edge]
end
return table.freeze(Queries)
