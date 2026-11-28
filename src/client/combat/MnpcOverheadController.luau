-- One local presentation owner for both moving actor kinds. Combat is read-only.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
local GameOptions = require(Shared:WaitForChild("GameOptions"))
local SpatialRoot = require(Shared:WaitForChild("character"):WaitForChild("CharacterSpatialRoot"))
local HealthBarView = require(script.Parent:WaitForChild("HealthBarView"))
local HealthUiSettings = require(script.Parent:WaitForChild("HealthUiSettings"))
local CameraController = require(script.Parent.Parent:WaitForChild("character"):WaitForChild("CameraController"))
local Registry = require(script.Parent:WaitForChild("MnpcOverheadRegistry"))
local Policy = require(script.Parent:WaitForChild("OverheadVisibilityPolicy"))
local Pool = require(script.Parent:WaitForChild("OverheadViewPool"))
local SelfOverhead = require(script.Parent:WaitForChild("SelfOverhead"))
local Controller = {}
local player = Players.LocalPlayer
local ELAPSED_STEP = 0.10
local AIM_CAMERA_MARGIN_STUDS = 64
local NEW_VIEWS_PER_TICK = 4
local reticleParams = RaycastParams.new()
reticleParams.FilterType = Enum.RaycastFilterType.Exclude
reticleParams.RespectCanCollide = false
local connections = {}
local pool, registry, own, style, currentGui
local started = false
local epoch = 0
local function reticleTarget(radius)
    local origin, direction = CameraController.GetAimRay()
    if not origin or not direction then return nil end
    local hit = Workspace:Raycast(origin, direction * (radius + AIM_CAMERA_MARGIN_STUDS), reticleParams)
    if not hit then return nil end
    local model = hit.Instance:FindFirstAncestorOfClass("Model")
    while model do
        local record = registry.ready[model]
        if record and record.kind == "Monster" then return model end
        local parent = model.Parent
        model = if parent and parent:IsA("Model") then parent
            elseif parent then parent:FindFirstAncestorOfClass("Model") else nil
    end
    return nil
end
local function syncGui()
    local gui = player:FindFirstChildOfClass("PlayerGui")
    if currentGui ~= gui then
        pool:Clear()
        own:Clear()
        currentGui = gui
    end
end
local function show(record, view, name, hp, icon, level, now, maxDistance)
    local ok, err = pcall(function()
        if maxDistance then view.SetMaxDistance(maxDistance) end
        if record.offsetDirty then
            view.RefreshVisualOffset()
            record.offsetDirty = nil
        end
        view.SetIcon(icon, level)
        view.SetSegments(name, hp)
    end)
    if not ok then
        pool:Release(record.model, now, true)
        record.retryAt = now + 2
        warn("[Overhead] presentation failed: " .. tostring(err))
    end
end
local function refresh()
    syncGui()
    local now = os.clock()
    pool:Expire(now)
    own:Step(player.Character, currentGui, style)
    if not currentGui then return end
    local character = player.Character
    local playerRoot = SpatialRoot.Get(player)
    local radius = math.clamp(tonumber(style.monster and style.monster.maxDistanceStuds) or 100, 20, 800)
    local profile = GameOptions.NpcOverheadSettings(HealthUiSettings.RuntimeDevice())
    reticleParams.FilterDescendantsInstances = if character then {character} else {}
    local context = {
        aimed = if playerRoot and next(registry.readyMonsters) ~= nil then reticleTarget(radius) else nil,
        locked = CameraController.AutoAimTarget(), userId = player.UserId,
        playerZone = character and character:GetAttribute("GameplayTestZone"),
        showAll = HealthUiSettings.ShowAllMonsters(), hpEnabled = style.monster.enabled == true,
        nameSq = profile.nameRadiusStuds ^ 2, hpSq = profile.healthRadiusStuds ^ 2,
    }
    local level = if character then tonumber(character:GetAttribute("Level")) or 1 else 1
    local pending = {}
    for model, record in pairs(registry.ready) do
        local distSq = math.huge
        if playerRoot then
            local delta = record.anchor.Position - playerRoot.Position
            distSq = delta:Dot(delta)
        end
        local name, hp, icon
        if record.kind == "Monster" then
            name, hp, icon = Policy.Monster(model, context, distSq <= radius * radius)
        else
            name, hp, icon = Policy.Npc(model, context, distSq)
        end
        local view = pool.active[model]
        if view and not view.IsAttached(currentGui) then
            pool:Release(model, now, true)
            view = nil
        end
        if not (name or hp or icon) then
            pool:Release(model, now)
            record.waitSince = nil
        elseif view then
            show(record, view, name, hp, icon, level, now)
            record.waitSince = nil
        elseif not record.retryAt or now >= record.retryAt then
            record.waitSince = record.waitSince or now
            table.insert(pending, {record=record, name=name, hp=hp, icon=icon, distance=distSq})
        end
    end
    -- Allocate only for the current eligibility snapshot. Existing idle views
    -- are free to reuse; no permanent active cap. Age cosmetic requests so they
    -- cannot starve behind a continuing stream of new combat targets.
    table.sort(pending, function(a, b)
        local ap = a.hp or now - a.record.waitSince >= 1
        local bp = b.hp or now - b.record.waitSince >= 1
        if ap ~= bp then return ap end
        if a.record.waitSince ~= b.record.waitSince then return a.record.waitSince < b.record.waitSince end
        return a.distance < b.distance
    end)
    local created = 0
    for _, request in ipairs(pending) do
        local record = request.record
        if #pool.idle == 0 then
            if created >= NEW_VIEWS_PER_TICK then break end
            created += 1
        end
        local view = pool:Acquire(record.model, currentGui, record.anchor, style, now)
        if view then
            record.retryAt, record.waitSince, record.offsetDirty = nil, nil, nil
            local maxDistance = if record.kind == "NPC" then math.max(profile.nameRadiusStuds, profile.healthRadiusStuds) + 80 else nil
            show(record, view, request.name, request.hp, request.icon, level, now, maxDistance)
        else
            record.retryAt = now + 2
        end
    end
end
function Controller.Start()
    if started then return end
    started = true
    epoch += 1
    local token = epoch
    style = HealthUiSettings.Current()
    pool = Pool.new(HealthBarView.Create, 8, 5)
    own = SelfOverhead.new(HealthBarView.Create)
    registry = Registry.new(Workspace, function(model)
        pool:Release(model, os.clock())
    end)
    registry:Start()
    table.insert(connections, HealthUiSettings.Changed(function()
        if not started or epoch ~= token then return end
        style = HealthUiSettings.Current()
        own:ApplyStyle(style)
        local profile = GameOptions.NpcOverheadSettings(HealthUiSettings.RuntimeDevice())
        for model, view in pairs(pool.active) do
            view.ApplyStyle(style)
            if registry.ready[model] and registry.ready[model].kind == "NPC" then
                view.SetMaxDistance(math.max(profile.nameRadiusStuds, profile.healthRadiusStuds) + 80)
            end
        end
        refresh()
    end))
    table.insert(connections, player.CharacterRemoving:Connect(function()
        if not started or epoch ~= token then return end
        pool:Clear(); own:Clear()
    end))
    table.insert(connections, player.CharacterAdded:Connect(function()
        if not started or epoch ~= token then return end
        pool:Clear(); own:Clear()
    end))
    table.insert(connections, player.ChildAdded:Connect(function(child)
        if not started or epoch ~= token then return end
        if child:IsA("PlayerGui") then syncGui() end
    end))
    table.insert(connections, player.ChildRemoved:Connect(function(child)
        if not started or epoch ~= token then return end
        if child:IsA("PlayerGui") then syncGui() end
    end))
    local elapsed = 0
    table.insert(connections, RunService.Heartbeat:Connect(function(dt)
        if not started or epoch ~= token then return end
        elapsed += dt
        if elapsed < ELAPSED_STEP then return end
        elapsed = 0
        refresh()
    end))
    refresh()
end
function Controller.Stop()
    if not started then return end
    started = false
    for _, connection in ipairs(connections) do connection:Disconnect() end
    table.clear(connections)
    registry:Stop()
    pool:Clear()
    own:Clear()
    registry, pool, own, currentGui, style = nil, nil, nil, nil, nil
end
return table.freeze(Controller)
