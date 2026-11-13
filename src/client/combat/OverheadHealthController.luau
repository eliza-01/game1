-- Visibility policy for player/monster overhead health. Server-owned HP and
-- MonsterTargetUserId replicate as attributes; this controller never writes them.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")
local HealthBarView = require(script.Parent:WaitForChild("HealthBarView"))
local HealthUiSettings = require(script.Parent:WaitForChild("HealthUiSettings"))
local CameraController = require(script.Parent.Parent:WaitForChild("character"):WaitForChild("CameraController"))

local Controller = {}
local player = Players.LocalPlayer
local started = false
local own: any = nil
local ownCharacter: Model? = nil
local ownDestroyConnection: RBXScriptConnection? = nil
local monsterViews: {[Model]: any} = {}
local pendingMonsters: {[Model]: boolean} = {}
local folderConnections: {RBXScriptConnection} = {}
local watchedFolder: Folder? = nil
local aimedMonster: Model? = nil
local ELAPSED_STEP = 0.10
local AIM_MAX_DISTANCE = 420

local function anchorFor(model: Model): BasePart?
    local anchor = model:FindFirstChild("RootCollider") or model:FindFirstChild("HumanoidRootPart")
        or model:FindFirstChild("NavigationRoot")
    return if anchor and anchor:IsA("BasePart") then anchor else nil
end

local function bindOwn(character: Model?)
    if ownDestroyConnection then ownDestroyConnection:Disconnect() end
    ownDestroyConnection = nil
    if own then own.Destroy(); own = nil end
    ownCharacter = character
    if not character then return end
    local function attach()
        if character ~= ownCharacter then return end
        local anchor = anchorFor(character)
        if anchor then
            if own then own.Destroy() end
            own = HealthBarView.Create(player:WaitForChild("PlayerGui"), character, anchor, HealthUiSettings.Current())
        end
    end
    attach()
    ownDestroyConnection = character.ChildAdded:Connect(function(child)
        if child.Name == "RootCollider" or child.Name == "HumanoidRootPart" then
            if not own then attach() end
        end
    end)
end

local function unbindMonster(model: Model)
    local view = monsterViews[model]
    if view then view.Destroy(); monsterViews[model] = nil end
    pendingMonsters[model] = nil
    if aimedMonster == model then aimedMonster = nil end
end

local function bindMonster(model: Instance)
    if not model:IsA("Model") or monsterViews[model] or pendingMonsters[model] then return end
    local monster = model :: Model
    pendingMonsters[monster] = true
    task.spawn(function()
        -- The spawner publishes the Model before it constructs RootCollider.
        local anchor = anchorFor(monster) or monster:WaitForChild("RootCollider", 5)
        if pendingMonsters[monster] and anchor and anchor:IsA("BasePart")
            and monster.Parent == watchedFolder and not monsterViews[monster] then
            monsterViews[monster] = HealthBarView.Create(player:WaitForChild("PlayerGui"), monster, anchor, HealthUiSettings.Current())
        end
        pendingMonsters[monster] = nil
    end)
end

local function watchFolder(folder: Folder)
    if watchedFolder == folder then return end
    for _, connection in ipairs(folderConnections) do connection:Disconnect() end
    table.clear(folderConnections)
    for model in pairs(monsterViews) do unbindMonster(model) end
    watchedFolder = folder
    table.insert(folderConnections, folder.ChildAdded:Connect(bindMonster))
    table.insert(folderConnections, folder.ChildRemoved:Connect(function(child)
        if child:IsA("Model") then unbindMonster(child) end
    end))
    for _, child in ipairs(folder:GetChildren()) do bindMonster(child) end
end

local function reticleTarget(): Model?
    local camera = Workspace.CurrentCamera
    if not camera then return nil end
    local size = camera.ViewportSize
    local cursor = CameraController.CursorPoint()
    local ray = camera:ViewportPointToRay(cursor.X * size.X, cursor.Y * size.Y)
    local params = RaycastParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    params.FilterDescendantsInstances = if player.Character then {player.Character} else {}
    params.RespectCanCollide = false
    local hit = Workspace:Raycast(ray.Origin, ray.Direction * AIM_MAX_DISTANCE, params)
    if not hit then return nil end
    local model = hit.Instance:FindFirstAncestorOfClass("Model")
    while model do
        if monsterViews[model] then return model end
        local parent = model.Parent
        model = if parent and parent:IsA("Model") then parent
            elseif parent then parent:FindFirstAncestorOfClass("Model") else nil
    end
    return nil
end

local function updateVisibility()
    local character = ownCharacter
    if own and character then
        local hp = tonumber(character:GetAttribute("HP")) or 0
        local maxHP = tonumber(character:GetAttribute("MaxHP")) or 0
        own.SetVisible(character:GetAttribute("LifeState") == "Alive"
            and (HealthUiSettings.IsPreviewing() or character:GetAttribute("InCombat") == true or hp < maxHP - 0.001))
    end
    local playerRoot = if character then anchorFor(character) else nil
    -- The radius is player-centered, not camera-centered (BillboardGui.MaxDistance
    -- uses the camera and would incorrectly shorten the range in third person).
    local style = HealthUiSettings.Current()
    local radius = math.clamp(tonumber(style.monster and style.monster.maxDistanceStuds) or 100, 20, 800)
    local radiusSquared = radius * radius
    aimedMonster = if playerRoot then reticleTarget() else nil
    for model, view in pairs(monsterViews) do
        local alive = model.Parent ~= nil and model:GetAttribute("LifeState") == "Alive"
        local focused = model == aimedMonster
        local attackingUs = model:GetAttribute("MonsterCombatActive") == true
            and model:GetAttribute("MonsterTargetUserId") == player.UserId
        local root = anchorFor(model)
        local delta = if playerRoot and root then root.Position - playerRoot.Position else nil
        local inRange = delta ~= nil and delta:Dot(delta) <= radiusSquared
        view.SetVisible(alive and inRange
            and (HealthUiSettings.IsPreviewing() or focused or attackingUs))
    end
end

function Controller.Start()
    if started then return end
    started = true
    HealthUiSettings.Changed(function()
        local style = HealthUiSettings.Current()
        if own then own.ApplyStyle(style) end
        for _, view in pairs(monsterViews) do view.ApplyStyle(style) end
        updateVisibility()
    end)
    player.CharacterAdded:Connect(bindOwn)
    player.CharacterRemoving:Connect(function(character)
        if character == ownCharacter then bindOwn(nil) end
    end)
    bindOwn(player.Character)
    local folder = Workspace:FindFirstChild("Monsters")
    if folder and folder:IsA("Folder") then watchFolder(folder) end
    Workspace.ChildAdded:Connect(function(child)
        if child.Name == "Monsters" and child:IsA("Folder") then watchFolder(child) end
    end)
    Workspace.ChildRemoved:Connect(function(child)
        if child == watchedFolder then
            for _, connection in ipairs(folderConnections) do connection:Disconnect() end
            table.clear(folderConnections)
            for model in pairs(monsterViews) do unbindMonster(model) end
            watchedFolder = nil
        end
    end)
    local elapsed = 0
    RunService.Heartbeat:Connect(function(dt)
        elapsed += dt
        if elapsed < ELAPSED_STEP then return end
        elapsed = 0
        updateVisibility()
    end)
end
return table.freeze(Controller)
