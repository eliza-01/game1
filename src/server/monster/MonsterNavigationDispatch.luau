local Trace=require(script.Parent:WaitForChild("MonsterNavigationTrace"))
local Config=require(script.Parent:WaitForChild("MonsterNavigationConfig"))
-- A/B switch: legacy implementation remains intact and published servers keep it.
local RunService=game:GetService("RunService")
local Workspace=game:GetService("Workspace")
local Legacy=require(script.Parent:WaitForChild("MonsterChaseNavigation"))
local Experimental=require(script.Parent:WaitForChild("MonsterExperimentalNavigation"))
local Speed=require(script.Parent:WaitForChild("MonsterNavigationSpeed"))
local Blocked=require(script.Parent:WaitForChild("MonsterBlockedPursuit"))
local Dispatch={}
function Dispatch.PresentationMultiplier(agent)
    return Speed.Multiplier(agent.recoveryNavigation,Config)
end
function Dispatch.IsBlockedRetreating(agent)
    return Blocked.IsRetreating(agent.recoveryNavigation)
end
function Dispatch.Enabled(agent)
    if not RunService:IsStudio() then return false end
    local override=Workspace:GetAttribute("Game1ExperimentalMonsterNavigation")
    if override==false or (override==nil and not Config.enabled) then return false end
    local kind=agent.model:GetAttribute("GameplayTestKind")
    return kind==nil or kind=="group" or (kind=="zone" and (tonumber(agent.model:GetAttribute("GameplayTestZone")) or 99)<=6)
end
function Dispatch.Prepare()
    if RunService:IsStudio() then Experimental.Initialize() end
end
Dispatch.Initialize=Legacy.Initialize
Dispatch.RunSpeedStuds=Legacy.RunSpeedStuds
function Dispatch.ClearPath(agent)
    if Trace.Enabled(agent) then
        local source,line=debug.info(2,"sl")
        local caller="caller="..tostring(source)..":"..tostring(line)
        if agent.recoveryNavigation then Trace.Event(agent,"CLEARPATH",caller,"mode="..tostring(agent.recoveryNavigation.mode))
        else Trace.Rate(agent,"CLEARPATH",1,caller) end
    end
    Experimental.Clear(agent); Legacy.ClearPath(agent)
end
function Dispatch.StopNavigation(agent)
    if Trace.Enabled(agent) then
        local source,line=debug.info(2,"sl")
        local caller="caller="..tostring(source)..":"..tostring(line)
        if agent.recoveryNavigation then Trace.Event(agent,"STOPNAVIGATION",caller,"mode="..tostring(agent.recoveryNavigation.mode))
        else Trace.Rate(agent,"STOPNAVIGATION",1,caller) end
    end
    Experimental.Clear(agent); Legacy.StopNavigation(agent)
end
function Dispatch.NavigateTo(agent,destination,speed)
    local enabled=Dispatch.Enabled(agent)
    if Trace.Enabled(agent) then Trace.Changed(agent,"BACKEND",enabled and "Experimental" or "Legacy","kind="..tostring(agent.model:GetAttribute("GameplayTestKind")),"zone="..tostring(agent.model:GetAttribute("GameplayTestZone")),"config="..tostring(Config.enabled),"override="..tostring(Workspace:GetAttribute("Game1ExperimentalMonsterNavigation"))) end
    if agent.experimentalNavigationEnabled~=enabled then
        Dispatch.StopNavigation(agent); agent.experimentalNavigationEnabled=enabled
        agent.model:SetAttribute("MonsterNavigationBackend",if enabled then "Experimental" else "Legacy")
    end
    if enabled then return Experimental.NavigateTo(agent,destination,speed) else Legacy.NavigateTo(agent,destination,speed) end
end
return table.freeze(Dispatch)
