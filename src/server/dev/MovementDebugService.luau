local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CharacterShared = Shared:WaitForChild("character")
local AnimationShared = Shared:WaitForChild("animation")
local CharacterMovementConfig = require(CharacterShared:WaitForChild("CharacterMovementConfig"))
local AnimationSpeedScaling = require(AnimationShared:WaitForChild("AnimationSpeedScaling"))

local MovementDebugService = {}
local started = false

local MIN_RUN_SPEED = 0
local MAX_RUN_SPEED = 500
local MONSTER_MODE_ATTRIBUTE = "Game1MonsterDebugLocomotionMode"
local MONSTER_RUNTIME_ATTRIBUTE = "Game1MonsterRuntime"
local MONSTER_LOCOMOTION_ATTRIBUTE = "MonsterLocomotionMode"
local RUN_SPEED_OVERRIDE_ATTRIBUTE = "MovementDebugRunSpeedOverride"
local MIN_ANIMATION_SPEED_PERCENT = AnimationSpeedScaling.MinPercent
local MAX_ANIMATION_SPEED_PERCENT = AnimationSpeedScaling.MaxPercent

local function finite(value: any, fallback: number): number
    local numeric = tonumber(value)
    if numeric == nil or numeric ~= numeric or numeric == math.huge or numeric == -math.huge then
        return fallback
    end
    return numeric
end

local function normalizeMonsterMode(value: any): string
    return string.lower(tostring(value or "")) == "run" and "Run" or "Walk"
end

local function ensureRemoteFolder(): Folder
    local folder = ReplicatedStorage:FindFirstChild("Game1Remotes")
    if folder and folder:IsA("Folder") then
        return folder
    end
    if folder then
        folder:Destroy()
    end
    folder = Instance.new("Folder")
    folder.Name = "Game1Remotes"
    folder.Parent = ReplicatedStorage
    return folder
end

local function ensureRemoteFunction(parent: Instance, name: string): RemoteFunction
    local current = parent:FindFirstChild(name)
    if current and current:IsA("RemoteFunction") then
        return current
    end
    if current then
        current:Destroy()
    end
    local remote = Instance.new("RemoteFunction")
    remote.Name = name
    remote.Parent = parent
    return remote
end

local function playerForCharacter(model: Model): Player?
    return Players:GetPlayerFromCharacter(model)
end

local function isMovementDebugModel(model: Model): boolean
    if tonumber(model:GetAttribute("RunSpeed")) == nil then
        return false
    end
    if playerForCharacter(model) then
        return true
    end
    if model:GetAttribute(MONSTER_RUNTIME_ATTRIBUTE) == true then
        return true
    end
    if model:GetAttribute("Game1NpcRuntime") == true or model:GetAttribute("NPCSlug") ~= nil then
        return true
    end
    return false
end

local function modelId(model: Model): string
    local owner = playerForCharacter(model)
    if owner then
        return "player:" .. tostring(owner.UserId)
    end
    if model:GetAttribute(MONSTER_RUNTIME_ATTRIBUTE) == true then
        local instanceId = tostring(model:GetAttribute("MonsterInstanceId") or model.Name)
        return "monster:" .. instanceId
    end
    local npcId = tostring(model:GetAttribute("NPCInstanceId") or model:GetAttribute("NPCSlug") or model:GetFullName())
    return "npc:" .. npcId
end

local function modelKind(model: Model): string
    if playerForCharacter(model) then
        return "player"
    end
    if model:GetAttribute(MONSTER_RUNTIME_ATTRIBUTE) == true then
        return "monster"
    end
    return "npc"
end

local function modelLabel(model: Model): string
    local owner = playerForCharacter(model)
    if owner then
        local archetype = tostring(model:GetAttribute("CharacterArchetype") or "character")
        return string.format("PLAYER · %s · %s", owner.DisplayName, archetype)
    end
    if model:GetAttribute(MONSTER_RUNTIME_ATTRIBUTE) == true then
        local slug = tostring(model:GetAttribute("MonsterSlug") or model.Name)
        local shortId = tostring(model:GetAttribute("MonsterInstanceId") or "")
        if #shortId > 7 then
            shortId = shortId:sub(-7)
        end
        return string.format("MONSTER · %s%s", slug, shortId ~= "" and (" · " .. shortId) or "")
    end
    local slug = tostring(model:GetAttribute("NPCSlug") or model.Name)
    return "NPC · " .. slug
end

local function collectModels(): {Model}
    local rows = {}
    local seen = {}
    for _, player in ipairs(Players:GetPlayers()) do
        local character = player.Character
        if character and isMovementDebugModel(character) then
            seen[character] = true
            table.insert(rows, character)
        end
    end
    for _, object in ipairs(Workspace:GetDescendants()) do
        if object:IsA("Model") and not seen[object] and isMovementDebugModel(object) then
            seen[object] = true
            table.insert(rows, object)
        end
    end
    table.sort(rows, function(left, right)
        return modelLabel(left) < modelLabel(right)
    end)
    return rows
end

local function findModelById(targetId: any): Model?
    local wanted = tostring(targetId or "")
    if wanted == "" then
        return nil
    end
    for _, model in ipairs(collectModels()) do
        if modelId(model) == wanted then
            return model
        end
    end
    return nil
end

local function movementModeFor(model: Model): string
    if model:GetAttribute(MONSTER_RUNTIME_ATTRIBUTE) == true then
        return normalizeMonsterMode(model:GetAttribute(MONSTER_LOCOMOTION_ATTRIBUTE))
    end
    return tostring(model:GetAttribute("AnimationMovementMode") or "Run") == "Walk" and "Walk" or "Run"
end

local function applyRuntimeRunSpeed(model: Model, runSpeed: number)
    model:SetAttribute(RUN_SPEED_OVERRIDE_ATTRIBUTE, runSpeed)
    if model:GetAttribute(MONSTER_RUNTIME_ATTRIBUTE) ~= true then
        -- Player/NPC stats can be recomputed by CharacterStatsService. Keep the
        -- debug value as the base too so the current Play-session override does
        -- not immediately snap back to the authored/default value.
        model:SetAttribute("BaseRunSpeed", runSpeed)
    end
    model:SetAttribute("RunSpeed", runSpeed)
    model:SetAttribute("MoveSpeed", runSpeed)

    local mode = movementModeFor(model)
    local resolved = CharacterMovementConfig.RobloxSpeed(model:GetAttribute("CharacterArchetype"), runSpeed, mode)

    local controllerManager = model:FindFirstChild("ControllerManager")
    if controllerManager and controllerManager:IsA("ControllerManager") then
        controllerManager.BaseMoveSpeed = resolved
    end

    local humanoid = model:FindFirstChildOfClass("Humanoid")
    if humanoid then
        humanoid.WalkSpeed = resolved
    end
end

local function animationChannelFor(model: Model): string
    local action = tostring(model:GetAttribute("AnimationActionSlot") or "")
    if action ~= "" then
        return string.lower(action)
    end
    local resolved = tostring(model:GetAttribute("AnimationResolvedSlot") or "")
    if resolved ~= "" then
        return string.lower(resolved)
    end
    local monsterState = tostring(model:GetAttribute("MonsterAnimationState") or "")
    if monsterState ~= "" then
        return string.lower(monsterState)
    end
    return string.lower(tostring(model:GetAttribute("MovementState") or "idle"))
end

local function unitRow(model: Model)
    local runSpeed = math.clamp(finite(model:GetAttribute("RunSpeed"), CharacterMovementConfig.DefaultRunSpeed), MIN_RUN_SPEED, MAX_RUN_SPEED)
    local animationOverride = tonumber(model:GetAttribute(AnimationSpeedScaling.DebugOverrideAttribute))
    local animationChannel = animationChannelFor(model)
    local animationSpeedPercent = AnimationSpeedScaling.ResolveForModel(model, animationChannel)
    return {
        id = modelId(model),
        label = modelLabel(model),
        kind = modelKind(model),
        model = model,
        runSpeed = runSpeed,
        walkSpeed = CharacterMovementConfig.ResolveSpeed(model:GetAttribute("CharacterArchetype"), runSpeed, "Walk"),
        runStudsPerSecond = CharacterMovementConfig.RobloxSpeed(model:GetAttribute("CharacterArchetype"), runSpeed, "Run"),
        walkStudsPerSecond = CharacterMovementConfig.RobloxSpeed(model:GetAttribute("CharacterArchetype"), runSpeed, "Walk"),
        animationSpeedPercent = animationSpeedPercent,
        animationSpeedOverride = animationOverride ~= nil,
        animationSlot = animationChannel,
        animationClip = tostring(model:GetAttribute("AnimationActionClip") or model:GetAttribute("AnimationResolvedClip") or ""),
        movementState = tostring(model:GetAttribute("MovementState") or model:GetAttribute("MonsterAnimationState") or ""),
        lifeState = tostring(model:GetAttribute("LifeState") or "Alive"),
    }
end

local function currentMonsterMode(): string
    return normalizeMonsterMode(Workspace:GetAttribute(MONSTER_MODE_ATTRIBUTE))
end

local function applyMonsterModeToModel(model: Model, mode: string)
    if model:GetAttribute(MONSTER_RUNTIME_ATTRIBUTE) == true then
        model:SetAttribute(MONSTER_LOCOMOTION_ATTRIBUTE, mode)
    end
end

local function applyMonsterModeToAll(mode: string)
    Workspace:SetAttribute(MONSTER_MODE_ATTRIBUTE, mode)
    local folder = Workspace:FindFirstChild("Monsters")
    if folder then
        for _, child in ipairs(folder:GetChildren()) do
            if child:IsA("Model") then
                applyMonsterModeToModel(child, mode)
            end
        end
    end
end

local function buildCatalog(player: Player)
    local units = {}
    local selectedId = ""
    local playerCharacter = player.Character
    if playerCharacter and isMovementDebugModel(playerCharacter) then
        selectedId = modelId(playerCharacter)
    end
    for _, model in ipairs(collectModels()) do
        table.insert(units, unitRow(model))
    end
    if selectedId == "" and units[1] then
        selectedId = units[1].id
    end
    return {
        units = units,
        selectedId = selectedId,
        monsterMode = currentMonsterMode(),
        minRunSpeed = MIN_RUN_SPEED,
        maxRunSpeed = MAX_RUN_SPEED,
        runSpeedUnitsPerStud = CharacterMovementConfig.RunSpeedUnitsPerStud,
        minAnimationSpeedPercent = MIN_ANIMATION_SPEED_PERCENT,
        maxAnimationSpeedPercent = MAX_ANIMATION_SPEED_PERCENT,
    }
end

local function applyUnit(_player: Player, targetId: any, patch: any)
    local model = findModelById(targetId)
    if not model then
        return { ok = false, error = "selected movement unit no longer exists" }
    end
    if type(patch) ~= "table" then
        return { ok = false, error = "movement debug patch must be a table" }
    end

    if patch.runSpeed ~= nil then
        local current = finite(model:GetAttribute("RunSpeed"), CharacterMovementConfig.DefaultRunSpeed)
        local runSpeed = math.clamp(finite(patch.runSpeed, current), MIN_RUN_SPEED, MAX_RUN_SPEED)
        applyRuntimeRunSpeed(model, runSpeed)
    end

    if patch.animationSpeedPercent ~= nil then
        local current = finite(model:GetAttribute(AnimationSpeedScaling.DebugOverrideAttribute), AnimationSpeedScaling.ResolveForModel(model, animationChannelFor(model)))
        local animationSpeedPercent = math.clamp(
            finite(patch.animationSpeedPercent, current),
            MIN_ANIMATION_SPEED_PERCENT,
            MAX_ANIMATION_SPEED_PERCENT
        )
        model:SetAttribute(AnimationSpeedScaling.DebugOverrideAttribute, animationSpeedPercent)
    end

    return {
        ok = true,
        unit = unitRow(model),
    }
end

local function setMonsterMode(_player: Player, requestedMode: any)
    local mode = normalizeMonsterMode(requestedMode)
    applyMonsterModeToAll(mode)
    return {
        ok = true,
        monsterMode = mode,
    }
end

function MovementDebugService.Start()
    if started or not RunService:IsStudio() then
        return
    end
    started = true

    applyMonsterModeToAll(currentMonsterMode())
    Workspace.DescendantAdded:Connect(function(object)
        if not object:IsA("Model") then
            return
        end
        task.defer(function()
            if object.Parent and object:GetAttribute(MONSTER_RUNTIME_ATTRIBUTE) == true then
                applyMonsterModeToModel(object, currentMonsterMode())
            end
        end)
    end)

    local remotes = ensureRemoteFolder()
    local catalog = ensureRemoteFunction(remotes, "GetMovementDebugCatalog")
    local apply = ensureRemoteFunction(remotes, "ApplyMovementDebug")
    local monsterMode = ensureRemoteFunction(remotes, "SetMovementDebugMonsterMode")
    catalog.OnServerInvoke = buildCatalog
    apply.OnServerInvoke = applyUnit
    monsterMode.OnServerInvoke = setMonsterMode
end

return table.freeze(MovementDebugService)
