-- NPC names have their own distance rule; HP appears only while damaged or
-- attacking the local player. Presentation-only: all HP/targets are server owned.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local GameOptions = require(Shared:WaitForChild("GameOptions"))
local HealthBarView = require(script.Parent:WaitForChild("HealthBarView"))
local HealthUiSettings = require(script.Parent:WaitForChild("HealthUiSettings"))

local Controller = {}
local player = Players.LocalPlayer
local views: {[Model]: any} = {}
local awaiting: {[Model]: {RBXScriptConnection}} = {}
local anchorConnections: {[Model]: RBXScriptConnection} = {}
local watched: Folder? = nil
local connections: {RBXScriptConnection} = {}
local started = false

local function disconnectPending(model: Model)
    local items = awaiting[model]
    awaiting[model] = nil
    if items then for _, item in ipairs(items) do item:Disconnect() end end
end

local function unbind(model: Model)
    local anchorConnection = anchorConnections[model]
    if anchorConnection then anchorConnection:Disconnect(); anchorConnections[model] = nil end
    disconnectPending(model)
    if views[model] then views[model].Destroy(); views[model] = nil end
end

local function bind(model: Instance)
    if not model:IsA("Model") or views[model] or awaiting[model] then return end
    local npc = model :: Model
    local signals: {RBXScriptConnection} = {}
    awaiting[npc] = signals
    local function tryBind()
        if npc.Parent ~= watched or views[npc] then return end
        if npc:GetAttribute("Game1NpcRuntime") ~= true
            or npc:GetAttribute("LifeState") == nil or npc:GetAttribute("NpcSlug") == nil then return end
        local anchor = npc:FindFirstChild("RootCollider")
        local gui = player:FindFirstChildOfClass("PlayerGui")
        if not anchor or not anchor:IsA("BasePart") or not gui then return end
        disconnectPending(npc)
        local view = HealthBarView.Create(gui, npc, anchor, HealthUiSettings.Current())
        views[npc] = view
        local radii = GameOptions.NpcOverheadSettings(HealthUiSettings.RuntimeDevice())
        view.SetMaxDistance(math.max(radii.nameRadiusStuds, radii.healthRadiusStuds) + 80)
        -- With StreamingEnabled the collider can vanish while its Model remains.
        anchorConnections[npc] = npc.ChildRemoved:Connect(function(child)
            if child == anchor then
                unbind(npc)
                if npc.Parent == watched then bind(npc) end
            end
        end)
    end
    table.insert(signals, player.ChildAdded:Connect(function(child)
        if child:IsA("PlayerGui") then tryBind() end
    end))
    table.insert(signals, npc.ChildAdded:Connect(tryBind))
    for _, attribute in ipairs({"Game1NpcRuntime", "LifeState", "NpcSlug"}) do
        table.insert(signals, npc:GetAttributeChangedSignal(attribute):Connect(tryBind))
    end
    tryBind()
end

local function watch(folder: Folder)
    if watched == folder then return end
    for _, signal in ipairs(connections) do signal:Disconnect() end
    table.clear(connections)
    for model in pairs(views) do unbind(model) end
    for model in pairs(awaiting) do disconnectPending(model) end
    watched = folder
    table.insert(connections, folder.ChildAdded:Connect(bind))
    table.insert(connections, folder.ChildRemoved:Connect(function(child)
        if child:IsA("Model") then unbind(child) end
    end))
    for _, child in ipairs(folder:GetChildren()) do bind(child) end
end

local function refresh()
    local character = player.Character
    local selfRoot = character and (character:FindFirstChild("RootCollider") or character:FindFirstChild("HumanoidRootPart"))
    local profile = GameOptions.NpcOverheadSettings(HealthUiSettings.RuntimeDevice())
    local nameSq = profile.nameRadiusStuds * profile.nameRadiusStuds
    local hpSq = profile.healthRadiusStuds * profile.healthRadiusStuds
    for model, view in pairs(views) do
        local root = model:FindFirstChild("RootCollider")
        local alive = model.Parent == watched and model:GetAttribute("LifeState") == "Alive"
        local distSq = math.huge
        if selfRoot and selfRoot:IsA("BasePart") and root and root:IsA("BasePart") then
            local delta = selfRoot.Position - root.Position
            distSq = delta:Dot(delta)
        end
        local maxHP = tonumber(model:GetAttribute("MaxHP")) or 0
        local hp = tonumber(model:GetAttribute("HP")) or maxHP
        local hostile = model:GetAttribute("NpcTargetUserId") == player.UserId
            and model:GetAttribute("NpcAIState") ~= "Idle"
        view.SetSegments(alive and distSq <= nameSq,
            alive and distSq <= hpSq and (hp < maxHP - 0.001 or hostile))
    end
end

function Controller.Start()
    if started then return end
    started = true
    local folder = Workspace:FindFirstChild("NPCs")
    if folder and folder:IsA("Folder") then watch(folder) end
    Workspace.ChildAdded:Connect(function(child)
        if child.Name == "NPCs" and child:IsA("Folder") then watch(child) end
    end)
    Workspace.ChildRemoved:Connect(function(child)
        if child == watched then
            for _, signal in ipairs(connections) do signal:Disconnect() end
            table.clear(connections)
            for model in pairs(views) do unbind(model) end
            for model in pairs(awaiting) do disconnectPending(model) end
            watched = nil
        end
    end)
    HealthUiSettings.Changed(function()
        for _, view in pairs(views) do view.ApplyStyle(HealthUiSettings.Current()) end
    end)
    local elapsed = 0
    RunService.Heartbeat:Connect(function(dt)
        elapsed += dt
        if elapsed < 0.1 then return end
        elapsed = 0
        refresh()
    end)
end
return table.freeze(Controller)
