-- One reversible live-rig demand owner for both MNPC domains.
-- Studio pilot only until client presentation and combat-reach admission are ready.
-- The existing ActorAIScheduler calls Step; no per-actor timer or new Heartbeat.
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")
local PlayerIndex = require(script.Parent:WaitForChild("PlayerSpatialIndex"))
local Root = require(script.Parent:WaitForChild("ActorTargetRoot"))
local Demand = {}
local records = {}
local activeBuild = nil
local STUDIO = RunService:IsStudio()
local ENTER = 512 -- pilot thresholds, NOT production combat/visual distances
local EXIT = 640
local HOLD = 5
local RETRY = 5
local READY_TIMEOUT = 15

local function enabled()
    return STUDIO and Workspace:GetAttribute("Game1MnpcDemandPilot") == true
end

local function pinned(agent)
    local model = agent.model
    local nav = agent.recoveryNavigation
    return (nav and (nav.plan or nav.climb or nav.blockedPursuit or nav.mode == "Retry" or nav.mode == "BlockedWait"))
        or agent.state ~= "Idle" or agent.target ~= nil or agent.attacking
        or agent.returning or agent.retaliating or agent.specialCast or agent.homeRecall
        or agent.retreatPending or agent.attackPursuitActive or agent.returnAfterAttack
        or (agent.recovery and agent.recovery:Pending())
        or model:GetAttribute("MonsterSpawning") == true
        or model:GetAttribute("MonsterCombatActive") == true
        or model:GetAttribute("InCombat") == true
        or model:GetAttribute("ActiveSkillEffects") ~= nil
end

local function nearby(root, radius)
    for _, player in ipairs(PlayerIndex.Query(root.Position, radius)) do
        local other = Root.Get(player.Character)
        if other then
            local delta = other.Position - root.Position
            -- Conservative horizontal distance; never sleep a rig on another floor nearby.
            if delta.X * delta.X + delta.Z * delta.Z <= radius * radius then return true end
        end
    end
    return false
end

function Demand.Register(model, callbacks)
    if not STUDIO then return end
    assert(records[model] == nil, "Duplicate MNPC demand owner")
    records[model] = {callbacks = callbacks, stage = "full", retryAt = 0}
end

function Demand.Remove(model)
    local record = records[model]
    if not record then return end
    records[model] = nil
    if activeBuild == record and record.stage ~= "loading" then activeBuild = nil end
    -- Keep the single admission slot until any yielding preparation returns.
end

local function current(model, record)
    return records[model] == record and model.Parent ~= nil and model:GetAttribute("LifeState") == "Alive"
end

local function release(model, record)
    local ok, result = pcall(record.callbacks.release)
    if not ok then
        -- A failed release may be partial: never silently mark the actor FULL.
        record.stage = "fault"
        warn("[game1][mnpc-demand] release failed: " .. tostring(result))
        return false
    end
    if result == false then return false end
    record.stage = "shell"
    record.farSince = nil
    model:SetAttribute("Game1MnpcDemandStage", "shell")
    return true
end

function Demand.Step(agent, now)
    local model = agent.model
    local record = records[model]
    if not record or not current(model, record) or record.stage == "fault" then return end
    if record.stage == "loading" then return end
    local pilot = enabled()
    -- Zero extra spatial queries on the ordinary FULL path.
    if not pilot and record.stage == "full" then record.farSince = nil; return end
    if record.stage == "preparing" then
        local ok, ready = pcall(record.callbacks.ready)
        if ok and ready then
            record.stage = "full"
            model:SetAttribute("Damageable", true)
            model:SetAttribute("Game1MnpcDemandStage", "full")
            if activeBuild == record then activeBuild = nil end
        elseif now >= record.readyUntil then
            if release(model, record) then record.retryAt = now + RETRY end
            if activeBuild == record then activeBuild = nil end
        end
        return
    end
    local radius = record.stage == "full" and EXIT or ENTER
    local wanted = not pilot or pinned(agent) or nearby(agent.root, radius)
    if record.stage == "full" then
        if wanted or not record.callbacks.canRelease() then record.farSince = nil; return end
        record.farSince = record.farSince or now
        if now - record.farSince >= HOLD then release(model, record) end
    elseif record.stage == "shell" and wanted and now >= record.retryAt and not activeBuild then
        activeBuild = record
        record.stage = "loading"
        model:SetAttribute("Game1MnpcDemandStage", "loading")
        task.spawn(function()
            local function alive() return current(model, record) end
            local ok, result = pcall(record.callbacks.acquire, alive)
            if alive() then
                if ok and result == true then
                    record.stage = "preparing"
                    record.readyUntil = os.clock() + READY_TIMEOUT
                    return -- hold admission until pose readiness or bounded timeout
                else
                    warn("[game1][mnpc-demand] acquire failed: " .. tostring(result))
                    if release(model, record) then record.retryAt = os.clock() + RETRY end
                end
            end
            if activeBuild == record then activeBuild = nil end
        end)
    end
end

return table.freeze(Demand)
