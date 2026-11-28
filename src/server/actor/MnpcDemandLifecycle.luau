-- Shared server pose demand, independent of each client's visual stage.
-- Existing AI scheduler owns observation/admission. No additional timer.
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
local GameOptions = require(Shared:WaitForChild("GameOptions"))
local World = Shared:WaitForChild("world")
local Policy = require(World:WaitForChild("MnpcLodPolicy"))
local Registry = require(World:WaitForChild("MnpcLodRegistry"))
local Attack = require(Shared:WaitForChild("combat"):WaitForChild("AttackConfig"))
local Balance = require(Shared:WaitForChild("balance"):WaitForChild("Balance"))
local DebugAccess = require(Shared:WaitForChild("dev"):WaitForChild("PublishedDebugAccess"))
local PlayerIndex = require(script.Parent:WaitForChild("PlayerSpatialIndex"))
local Root = require(script.Parent:WaitForChild("ActorTargetRoot"))
local Demand = {}
local records, pending = {}, {}
local activeBuild = nil
local qualified = setmetatable({}, {__mode = "k"})
local HOLD, RETRY, READY_TIMEOUT = 5, 5, 15
local PREWARM, RELEASE_MARGIN = 48, 32
-- Cover all equip choices, not only the currently held weapon. Debug loadouts
-- can raise range up to MaxAimDistance; never use a smaller admission radius.
local maxReach = Attack.Range
for _, row in ipairs(Balance.Weapons) do
    local radius = tonumber(row.radius)
    if radius and radius == radius then maxReach = math.max(maxReach, radius) end
end
maxReach = math.clamp(maxReach, 1, Attack.MaxAimDistance)
if DebugAccess.ServerEnabled() then maxReach = Attack.MaxAimDistance end

local function enabled()
    -- Persisted Options is the sole authority; no per-Place override.
    return GameOptions.MnpcDemandEnabled()
end

local function profileOf(model)
    local kind = model:GetAttribute("Game1MnpcKind")
    local key = Policy.Key(kind, model:GetAttribute(kind == "NPC" and "NpcSlug" or "MonsterSlug"))
    local entry = key and Registry.actors[key]
    return key and (entry and entry.profile or Registry.defaults), key
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
        or model:GetAttribute("Game1GameplayTestOwner") ~= nil
end

local function positive(value)
    local n = tonumber(value)
    return n and n == n and n >= 0 and n < math.huge and n or 0
end

local function radiusFor(model, profile, full)
    local collider = model:FindFirstChild("RootCollider")
    local extent = collider and collider.Size.Magnitude * 0.5 or 0
    local base = math.max(profile.full + profile.hysteresis, maxReach + extent + 8,
        positive(model:GetAttribute("MonsterAggroRadius")), positive(model:GetAttribute("MonsterAttackRadius")),
        positive(model:GetAttribute("NpcAttackRadius")))
    return base + PREWARM + (full and RELEASE_MARGIN or 0)
end

local function nearest(root, radius)
    local result = math.huge
    for _, player in ipairs(PlayerIndex.Query(root.Position, radius)) do
        local other = Root.Get(player.Character)
        if other then
            local delta = other.Position - root.Position
            local distance = math.sqrt(delta.X * delta.X + delta.Z * delta.Z)
            if distance <= radius then result = math.min(result, distance) end
        end
    end
    return result
end

-- Only a previously validated effective rig/loadout may skip initial FULL.
-- First instance of every type takes the original spawn/validation path.
function Demand.CanSpawnShell(model, root, template)
    if not enabled() then return false end
    local profile, key = profileOf(model)
    local keys = qualified[template]
    return Policy.Valid(profile) and profile.enabled and keys ~= nil and keys[key] == true
        and nearest(root, radiusFor(model, profile, true)) == math.huge
end

function Demand.Register(model, callbacks, initialShell, template)
    assert(records[model] == nil, "Duplicate MNPC demand owner")
    local stage = initialShell and "shell" or "full"
    records[model] = {callbacks = callbacks, stage = stage, retryAt = 0, template = template, model = model}
    model:SetAttribute("Game1MnpcDemandStage", stage)
end

function Demand.Remove(model)
    local record = records[model]
    if not record then return end
    records[model], pending[record] = nil, nil
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
        model:SetAttribute("Damageable", false)
        model:SetAttribute("Game1MnpcDemandStage", "fault")
        warn("[game1][mnpc-demand] release failed: " .. tostring(result))
        return false
    end
    if result == false then
        if record.stage ~= "full" then
            record.stage = "fault"
            model:SetAttribute("Damageable", false)
            model:SetAttribute("Game1MnpcDemandStage", "fault")
        end
        return false
    end
    record.stage = "shell"
    record.farSince = nil
    model:SetAttribute("Game1MnpcDemandStage", "shell")
    return true
end

local function need(agent, full)
    local profile = profileOf(agent.model)
    if not enabled() or not Policy.Valid(profile) or not profile.enabled then return true, 0 end
    local distance = nearest(agent.root, radiusFor(agent.model, profile, full))
    if pinned(agent) then return true, distance == math.huge and 0 or distance end
    return distance < math.huge, distance
end

function Demand.Step(agent, now)
    local model = agent.model
    local record = records[model]
    if not record or not current(model, record) or record.stage == "fault" then return end
    if record.stage == "loading" then return end
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
    -- Disabled ordinary FULL path incurs no additional spatial query.
    if not enabled() and record.stage == "full" then record.farSince = nil; return end
    local wanted, distance = need(agent, record.stage == "full")
    if record.stage == "full" then
        if wanted or not record.callbacks.canRelease() then record.farSince = nil; return end
        -- Qualification is established only after native readiness and the
        -- original successful FULL path, and is scoped to this template/type.
        local _, key = profileOf(model)
        if record.template and key then
            local keys = qualified[record.template] or {}
            keys[key] = true
            qualified[record.template] = keys
        end
        record.farSince = record.farSince or now
        if now - record.farSince >= HOLD then release(model, record) end
    elseif record.stage == "shell" then
        if wanted and now >= record.retryAt then
            pending[record] = {agent = agent, distance = distance}
        else
            pending[record] = nil
        end
    end
end

-- One nearest-first admission after the existing AI batch, not whichever
-- actor happens to have the earliest AI deadline. Revalidate pending requests.
function Demand.Pump()
    if activeBuild then return end
    local best, bestDistance = nil, math.huge
    for record, request in pairs(pending) do
        local model = record.model
        if not current(model, record) or record.stage ~= "shell" then
            pending[record] = nil
        else
            local wanted, distance = need(request.agent, false)
            if not wanted then pending[record] = nil
            elseif not best or distance < bestDistance then
                best, bestDistance = record, distance
            end
        end
    end
    if not best then return end
    local record, model = best, best.model
    pending[record] = nil
    activeBuild = record
    record.stage = "loading"
    model:SetAttribute("Game1MnpcDemandStage", "loading")
    task.spawn(function()
        local function alive() return current(model, record) end
        local ok, result = pcall(record.callbacks.acquire, alive)
        if alive() then
            if ok and result == true then
                record.stage = "preparing"
                model:SetAttribute("Game1MnpcDemandStage", "preparing")
                record.readyUntil = os.clock() + READY_TIMEOUT
                return
            end
            warn("[game1][mnpc-demand] acquire failed: " .. tostring(result))
            if release(model, record) then record.retryAt = os.clock() + RETRY end
        end
        if activeBuild == record then activeBuild = nil end
    end)
end

return table.freeze(Demand)
