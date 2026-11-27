local Queries=require(script.Parent:WaitForChild("MonsterRescueQueries"))
local Sampling=require(script.Parent:WaitForChild("MonsterRescueSampling"))
local function find(ctx,line)
    if ctx.entryPlans[line]~=nil then return ctx.entryPlans[line] or nil end
    local entry=Sampling.Find(ctx,line,function(candidate)
        ctx.stats.entryCandidates=ctx.stats.entryCandidates+1
        if not Queries.Check(ctx,"entry",candidate) then return false end
        ctx.stats.entries=ctx.stats.entries+1
        return true
    end)
    local result=entry and {[entry.edge]=entry} or false
    ctx.entryPlans[line]=result
    return result or nil
end
return table.freeze({Find=find})
