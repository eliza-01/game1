-- Visibility policy for player/monster overhead health. Server-owned HP and
-- MonsterTargetUserId replicate as attributes; this controller never writes them.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")
local HealthBarView = require(script.Parent:WaitForChild("HealthBarView"))
local HealthUiSettings = require(script.Parent:WaitForChild("HealthUiSettings"))
local CameraController = require(script.Parent.Parent:WaitForChild("character"):WaitForChild("CameraController"))

local LocalVisibility = require(script.Parent.Parent:WaitForChild("actor"):WaitForChild("MnpcLocalVisibility"))
local Controller = {}
local player = Players.LocalPlayer
local started = false
local own: any = nil
local ownCharacter: Model? = nil
local ownDestroyConnection: RBXScriptConnection? = nil
local monsterViews: {[Model]: any} = {}
local pendingMonsters: {[Model]: {connections: {RBXScriptConnection}}} = {}
local anchorRemovedConnections: {[Model]: RBXScriptConnection} = {}
local folderConnections: {RBXScriptConnection} = {}
local watchedFolder: Folder? = nil
local aimedMonster: Model? = nil
local detachedMonsters: {Model} = {}
local ELAPSED_STEP = 0.10
-- The camera can sit behind/beside the player's root in third person.
-- Cast past the player-centered display radius, not an unrelated fixed cap.
local AIM_CAMERA_MARGIN_STUDS = 64
local reticleParams = RaycastParams.new()
reticleParams.FilterType = Enum.RaycastFilterType.Exclude
reticleParams.RespectCanCollide = false

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
    -- The ray ignores the current character, including after respawn.
    reticleParams.FilterDescendantsInstances = if character then {character} else {}
    if not character then return end
    local function attach()
        if character ~= ownCharacter then return end
        local anchor = anchorFor(character)
        local gui = player:FindFirstChildOfClass("PlayerGui")
        if anchor and gui then
            if own then own.Destroy() end
            own = HealthBarView.Create(gui, character, anchor, HealthUiSettings.Current())
        end
    end
    attach()
    ownDestroyConnection = character.ChildAdded:Connect(function(child)
        if child.Name == "RootCollider" or child.Name == "HumanoidRootPart"
            or child.Name == "NavigationRoot" then
            if not own then attach() end
        end
    end)
end

local function clearPendingMonster(model: Model)
    local connections = pendingMonsters[model]
    if not connections then return end
    pendingMonsters[model] = nil
    for _, connection in ipairs(connections.connections) do connection:Disconnect() end
end

local function unbindMonster(model: Model)
    local removed = anchorRemovedConnections[model]
    if removed then removed:Disconnect(); anchorRemovedConnections[model] = nil end
    clearPendingMonster(model)
    local view = monsterViews[model]
    if view then view.Destroy(); monsterViews[model] = nil end
    if aimedMonster == model then aimedMonster = nil end
end

local function bindMonster(model: Instance)
    if not model:IsA("Model") or monsterViews[model] or pendingMonsters[model] then return end
    local monster = model :: Model
    -- The server parents the model BEFORE publishing its attributes and its
    -- navigation/collision root. Attribute and part replication can arrive in
    -- either order, especially when StreamingEnabled is on. Do not time out.
    local connections: {RBXScriptConnection} = {}
    local function attachWhenReady()
        if monster.Parent ~= watchedFolder or monsterViews[monster] then return end
        if monster:GetAttribute("Game1MonsterRuntime") ~= true
            or monster:GetAttribute("LifeState") == nil
            or type(monster:GetAttribute("MonsterSlug")) ~= "string" then return end
        -- Wait for the actual combat/visual collider, not the early
        -- navigation root, which can arrive before the full monster rig.
        local anchor = monster:FindFirstChild("RootCollider")
        if not anchor or not anchor:IsA("BasePart") then return end
        local playerGui = player:FindFirstChildOfClass("PlayerGui")
        if not playerGui then return end
        -- Keep pending watchers alive until construction succeeded. If the
        -- UI has not finished initializing, another readiness event can retry.
        local view = HealthBarView.Create(playerGui, monster, anchor, HealthUiSettings.Current())
        monsterViews[monster] = view
        clearPendingMonster(monster)
        -- Streaming can remove a PART while leaving the Model alive. Reattach
        -- the existing UI policy when its adornee is streamed back in.
        anchorRemovedConnections[monster] = monster.ChildRemoved:Connect(function(child)
            if child == anchor then
                unbindMonster(monster)
                if monster.Parent == watchedFolder then bindMonster(monster) end
            end
        end)
    end
    -- One shared PlayerGui listener in Start() retries all pending monsters;
    -- never install a player listener per monster (MMO population scale).
    pendingMonsters[monster] = {connections = connections}
    table.insert(connections, monster.ChildAdded:Connect(function(child)
        if child.Name == "RootCollider" or child.Name == "HumanoidRootPart"
            or child.Name == "NavigationRoot" then
            attachWhenReady()
        end
    end))
    for _, attribute in ipairs({"Game1MonsterRuntime", "MonsterSlug", "LifeState"}) do
        table.insert(connections, monster:GetAttributeChangedSignal(attribute):Connect(attachWhenReady))
    end
    attachWhenReady()
end

local function rebindForPlayerGui()
    -- The monster remains alive across a player's respawn, while its client
    -- BillboardGui may have been destroyed with the previous PlayerGui.
    -- Rebuild only at the rare GUI identity transition, not every frame.
    for model in pairs(monsterViews) do unbindMonster(model) end
    for model in pairs(pendingMonsters) do clearPendingMonster(model) end
    if watchedFolder then
        for _, child in ipairs(watchedFolder:GetChildren()) do bindMonster(child) end
    end
end

local function watchFolder(folder: Folder)
    if watchedFolder == folder then return end
    for _, connection in ipairs(folderConnections) do connection:Disconnect() end
    table.clear(folderConnections)
    for model in pairs(monsterViews) do unbindMonster(model) end
    for model in pairs(pendingMonsters) do clearPendingMonster(model) end
    watchedFolder = folder
    table.insert(folderConnections, folder.ChildAdded:Connect(bindMonster))
    table.insert(folderConnections, folder.ChildRemoved:Connect(function(child)
        if child:IsA("Model") then unbindMonster(child) end
    end))
    for _, child in ipairs(folder:GetChildren()) do bindMonster(child) end
end

local function reticleTarget(radius: number): Model?
    -- Same aim ray as camera, Bow and AttackController: no mismatched
    -- viewport calculation or camera-to-character offset.
    local origin, direction = CameraController.GetAimRay()
    if not origin or not direction then return nil end
    local hit = Workspace:Raycast(origin, direction * (radius + AIM_CAMERA_MARGIN_STUDS), reticleParams)
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
    aimedMonster = if playerRoot and next(monsterViews) ~= nil then reticleTarget(radius) else nil
    -- A locked mobile camera deliberately tracks this same live monster; do
    -- not lose its HP just because the collider briefly misses a ray sample.
    local lockedMonster = CameraController.AutoAimTarget()
    local currentGui = player:FindFirstChildOfClass("PlayerGui")
    local playerZone = if character then character:GetAttribute("GameplayTestZone") else nil
    local playerLevel = if character then tonumber(character:GetAttribute("Level")) or 1 else 1
    for model, view in pairs(monsterViews) do
        -- Some spawn/reset paths remove BillboardGui while the monster Model
        -- stays in Workspace. Recover from missing adornee or destroyed GUI.
        if not view.IsAttached(currentGui) then
            table.insert(detachedMonsters, model)
            continue
        end
        local alive = model.Parent == watchedFolder and model:GetAttribute("LifeState") == "Alive" and LocalVisibility.Full(model)
            and model:GetAttribute("MonsterHomeRecalling") ~= true
        local focused = model == aimedMonster or model == lockedMonster
        -- The server's current target is the authority. Aggro/Chase/Attack
        -- all keep this attribute until the monster actually leaves combat.
        local attackingUs = model:GetAttribute("MonsterCombatActive") == true
            and model:GetAttribute("MonsterTargetUserId") == player.UserId
        local root = anchorFor(model)
        local delta = if playerRoot and root then root.Position - playerRoot.Position else nil
        local inRange = delta ~= nil and delta:Dot(delta) <= radiusSquared
        local zone = model:GetAttribute("GameplayTestZone")
        local release = typeof(zone) == "number" and zone <= 6
        local sameZone = release and playerZone == zone and model:GetAttribute("Game1GameplayTestOwner") == player.UserId
        local group = model:GetAttribute("GameplayTestKind") == "group"
            and model:GetAttribute("Game1GameplayTestOwner") == player.UserId
        view.SetIcon(alive and (sameZone or (group and inRange)), playerLevel)
        if group then
            view.SetSegments(alive and inRange, alive and inRange
                and (HealthUiSettings.ShowAllMonsters() or focused or attackingUs))
        elseif release then
            -- Portraits across the current zone; titles only nearby; HP when engaged.
            view.SetSegments(alive and sameZone and inRange, alive and sameZone and inRange
                and (HealthUiSettings.ShowAllMonsters() or focused or attackingUs))
        else
            view.SetVisible(alive and inRange and (HealthUiSettings.ShowAllMonsters() or focused or attackingUs))
        end
    end
    -- Rebind after the iteration: never mutate the live hash while visiting it.
    for _, model in ipairs(detachedMonsters) do
        unbindMonster(model)
        if model.Parent == watchedFolder then bindMonster(model) end
    end
    table.clear(detachedMonsters)
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
    player.ChildAdded:Connect(function(child)
        if child:IsA("PlayerGui") then
            bindOwn(ownCharacter)
            rebindForPlayerGui()
        end
    end)
    player.ChildRemoved:Connect(function(child)
        if child:IsA("PlayerGui") then
            if own then own.Destroy(); own = nil end
            rebindForPlayerGui()
        end
    end)
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
            for model in pairs(pendingMonsters) do clearPendingMonster(model) end
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
