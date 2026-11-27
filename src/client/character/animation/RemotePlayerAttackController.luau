-- Reconstruct the server-accepted upper-body attack on observers. Bone.Transform
-- on the owner's local sampler is not replicated by Roblox. Locomotion stays
-- on the real, natively replicated Animator; the owner is never played twice.
local Players = game:GetService("Players")
local HttpService = game:GetService("HttpService")
local Workspace = game:GetService("Workspace")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Phase = require(ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("combat"):WaitForChild("AttackPresentationPhase"))
local Composer = require(script.Parent:WaitForChild("AttackUpperBodyComposer"))
local Controller = {}
local ATTRIBUTE = Phase.Attribute
local entries = {}
local playerConnections = {}
local started = false

local function decode(model)
    local raw = model:GetAttribute(ATTRIBUTE)
    if type(raw) ~= "string" then return nil end
    local ok, state = pcall(HttpService.JSONDecode, HttpService, raw)
    if not ok or type(state) ~= "table" or type(state.serial) ~= "number"
        or type(state.animationId) ~= "string" or type(state.duration) ~= "number" or state.duration <= 0
        or type(state.startAt) ~= "number" or type(state.endAt) ~= "number" then return nil end
    return state
end

local function stop(entry)
    entry.generation += 1
    entry.state = nil
    entry.track = nil
    entry.composer.End()
end

local function eligible(entry): boolean
    return entry.player.Character == entry.model and entry.model.Parent ~= nil
        and entry.model:GetAttribute("LifeState") == "Alive"
        and entry.model:GetAttribute("SkillStunned") ~= true
end

local function align(entry)
    local state, track = entry.state, entry.track
    if not state or not track then return end
    local phase, rate = Phase.Resolve(state, Workspace:GetServerTimeNow())
    entry.composer.SeekPhase(phase, track.Length / state.duration * rate)
    local fade = entry.composer.GetExitBlendSeconds()
    task.delay(math.max(0, state.endAt - Workspace:GetServerTimeNow() - fade), function()
        if entry.state == state and entry.track == track then entry.composer.BeginExitBlend() end
    end)
    task.delay(math.max(0, state.endAt - Workspace:GetServerTimeNow()), function()
        if entry.state == state then stop(entry) end
    end)
end

local function refresh(entry)
    local state = decode(entry.model)
    if not eligible(entry) or not state or state.endAt <= Workspace:GetServerTimeNow() then stop(entry); return end
    if entry.state and entry.state.serial == state.serial then
        -- Bounce is the only same-serial update. If loading is in progress,
        -- the completion callback will align against the latest snapshot.
        if entry.state.bounceAt == state.bounceAt then return end
        entry.state = state
        align(entry)
        return
    end
    stop(entry)
    entry.state = state
    local generation = entry.generation
    local weapon = entry.model:GetAttribute("EquippedWeaponType")
    entry.weapon = weapon
    task.spawn(function()
        local function valid()
            return entry.generation == generation and eligible(entry) and entry.state ~= nil
                and entry.state.endAt > Workspace:GetServerTimeNow()
        end
        -- Model replication may follow the initial attribute; wait only within
        -- the accepted attack interval. No continuous polling when idle.
        while valid() and not entry.model:FindFirstChild("Visual") do task.wait(0.05) end
        if not valid() then return end
        local track, reason = entry.composer.Begin(entry.model, state, 1, valid, state.duration)
        if not valid() then
            if entry.generation == generation then stop(entry) end
            return
        end
        if not track then
            warn("[game1][remote-attack] visual unavailable: " .. tostring(reason))
            stop(entry)
            return
        end
        entry.track = track
        align(entry)
    end)
end

local function unbind(player)
    local entry = entries[player]
    if not entry then return end
    entries[player] = nil
    stop(entry)
    for _, connection in ipairs(entry.connections) do connection:Disconnect() end
end

local function bind(player, model)
    unbind(player)
    if player == Players.LocalPlayer then return end
    local entry = {player = player, model = model, composer = Composer.NewObserver(), generation = 0, connections = {}}
    entries[player] = entry
    local function watch(attribute, fn)
        table.insert(entry.connections, model:GetAttributeChangedSignal(attribute):Connect(fn))
    end
    watch(ATTRIBUTE, function() refresh(entry) end)
    watch("LifeState", function() if not eligible(entry) then stop(entry) else refresh(entry) end end)
    watch("SkillStunned", function() if not eligible(entry) then stop(entry) end end)
    watch("EquippedWeaponType", function() if entry.state and entry.weapon ~= model:GetAttribute("EquippedWeaponType") then stop(entry) end end)
    watch("EquippedWeaponBalanceId", function() if entry.state then stop(entry) end end)
    table.insert(entry.connections, model.Destroying:Connect(function() if entries[player] == entry then unbind(player) end end))
    table.insert(entry.connections, model.AncestryChanged:Connect(function()
        if entries[player] == entry then refresh(entry) end
    end))
    refresh(entry)
end

local function watchPlayer(player)
    if player == Players.LocalPlayer or playerConnections[player] then return end
    playerConnections[player] = {
        player.CharacterAdded:Connect(function(model) bind(player, model) end),
        player.CharacterRemoving:Connect(function(model) if entries[player] and entries[player].model == model then unbind(player) end end),
    }
    if player.Character then bind(player, player.Character) end
end

function Controller.Start()
    if started then return end
    started = true
    Players.PlayerAdded:Connect(watchPlayer)
    Players.PlayerRemoving:Connect(function(player)
        unbind(player)
        for _, connection in ipairs(playerConnections[player] or {}) do connection:Disconnect() end
        playerConnections[player] = nil
    end)
    for _, player in ipairs(Players:GetPlayers()) do watchPlayer(player) end
end

return table.freeze(Controller)
