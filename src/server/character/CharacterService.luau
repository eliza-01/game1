local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local InsertService = game:GetService("InsertService")
local ServerStorage = game:GetService("ServerStorage")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CharacterShared = Shared:WaitForChild("character")
local CharacterMovementConfig = require(CharacterShared:WaitForChild("CharacterMovementConfig"))
local CharacterRegistry = require(CharacterShared:WaitForChild("CharacterRegistry"))
local BootstrapConfig = require(CharacterShared:WaitForChild("BootstrapConfig"))

local CharacterRigService = require(script.Parent:WaitForChild("CharacterRigService"))
local CharacterStatsService = require(script.Parent:WaitForChild("CharacterStatsService"))
local CombatRoot = script.Parent.Parent:WaitForChild("combat")
local EntityHitboxService = require(CombatRoot:WaitForChild("EntityHitboxService"))

local CharacterService = {}
local started = false
local spawning: { [Player]: boolean } = {}

local cache = ServerStorage:FindFirstChild("game1CharacterCache") or Instance.new("Folder")
cache.Name = "game1CharacterCache"
cache.Parent = ServerStorage

local function findArchetype(archetypeId: string?): any?
    if not archetypeId or archetypeId == "" then
        return nil
    end
    for _, row in ipairs(CharacterRegistry.archetypes or {}) do
        if tostring(row.id) == archetypeId then
            return row
        end
    end
    return nil
end

local function registeredAssetId(row: any?): number?
    if not row then
        return nil
    end
    if type(row.model) == "table" then
        return tonumber(row.model.assetId)
    end
    return tonumber(row.modelAssetId)
end

local function selectedCharacter(): (any?, number?, string, string, string?, string?, string?)
    local requestedId = tostring(CharacterRegistry.activeArchetypeId or "")
    local row = findArchetype(requestedId)
    local assetId = registeredAssetId(row)
    if row and assetId then
        return row,
            assetId,
            tostring(row.id),
            tostring(row.displayName or row.id),
            requestedId,
            tostring(row.race or ""),
            tostring(row.gender or "")
    end
    return nil,
        tonumber(BootstrapConfig.CharacterModelAssetId),
        "bootstrap",
        BootstrapConfig.CharacterLabel,
        requestedId ~= "" and requestedId or nil,
        nil,
        nil
end

local function getAssetTemplate(assetId: number, cacheKey: string): Model?
    local cached = cache:FindFirstChild(cacheKey)
    if cached and cached:IsA("Model") then
        return cached
    end

    local ok, bundle = pcall(InsertService.LoadAsset, InsertService, assetId)
    if not ok or not bundle then
        warn("[game1] cannot load character asset", assetId, bundle)
        return nil
    end

    local imported: Instance = bundle
    local children = bundle:GetChildren()
    if bundle:IsA("Model") and #children == 1 then
        imported = children[1]
        imported.Parent = nil
        bundle:Destroy()
    end

    local template: Model
    if imported:IsA("Model") then
        template = imported
    else
        template = Instance.new("Model")
        imported.Parent = template
    end
    template.Name = cacheKey
    template.Parent = cache
    return template
end

local function findRegisteredTemplate(row: any): Model?
    local node: Instance = ServerStorage
    for _, segment in {
        "characters",
        tostring(row.race or ""),
        tostring(row.gender or ""),
        tostring(row.id or ""),
        "model",
    } do
        if segment == "" then
            node = ServerStorage
            break
        end
        local child = node:FindFirstChild(segment)
        if not child then
            node = ServerStorage
            break
        end
        node = child
    end
    if node ~= ServerStorage then
        local named = node:FindFirstChild(tostring(row.id or ""))
        if named and named:IsA("Model") then
            return named
        end
        local model = node:FindFirstChildWhichIsA("Model")
        if model then
            return model
        end
    end

    -- m3 stored the first registered model directly under ServerStorage.
    -- Keep reading that saved-place layout until it is explicitly migrated.
    for _, name in { tostring(row.displayName or ""), tostring(row.id or "") } do
        if name ~= "" then
            local direct = ServerStorage:FindFirstChild(name)
            if direct and direct:IsA("Model") then
                return direct
            end
        end
    end
    return nil
end

local function templateFor(row: any?, assetId: number): Model?
    if row then
        local stored = findRegisteredTemplate(row)
        if stored then
            return stored
        end
        warn(("[game1] registered character %s is not in ServerStorage; loading published asset %d")
            :format(tostring(row.id), assetId))
        return getAssetTemplate(assetId, "registered-" .. tostring(assetId))
    end
    return getAssetTemplate(assetId, "bootstrap-" .. tostring(assetId))
end

local function destroyPreviousCharacter(player: Player)
    local previous = player.Character
    if previous then
        EntityHitboxService.Detach(previous)
        player.Character = nil
        previous:Destroy()
    end
end

local function createCharacter(player: Player): Model?
    if spawning[player] then
        return nil
    end
    spawning[player] = true

    local row, assetId, archetype, label, requestedArchetype, race, gender = selectedCharacter()
    if not assetId then
        spawning[player] = nil
        return nil
    end

    local template = templateFor(row, assetId)
    if not template and row then
        assetId = tonumber(BootstrapConfig.CharacterModelAssetId)
        archetype = "bootstrap"
        label = BootstrapConfig.CharacterLabel
        race = nil
        gender = nil
        template = assetId and templateFor(nil, assetId) or nil
    end
    if not template then
        spawning[player] = nil
        return nil
    end

    destroyPreviousCharacter(player)

    local character = Instance.new("Model")
    character.Name = player.Name
    character:SetAttribute("CharacterArchetype", archetype)
    character:SetAttribute("CharacterDisplayName", label)
    character:SetAttribute("CharacterRace", race or "")
    character:SetAttribute("CharacterGender", gender or "")
    character:SetAttribute("CharacterSkeletonSignature", if row and row.skeleton then tostring(row.skeleton.signature or "") else "")
    character:SetAttribute("AnimationProfileId", archetype)
    character:SetAttribute("AnimationWeaponSet", "hands")
    character:SetAttribute("RequestedCharacterArchetype", requestedArchetype or "")
    character:SetAttribute("UsingBootstrapVisual", archetype == "bootstrap")
    character:SetAttribute("CharacterOwnerUserId", player.UserId)
    character:SetAttribute("CustomCharacter", true)
    character:SetAttribute("MoveSpeed", CharacterMovementConfig.DefaultRunSpeed)
    character:SetAttribute("AnimationMovementMode", "Run")
    character:SetAttribute("AnimationMovementDirection", "Forward")
    character:SetAttribute("MovementState", "Idle")
    character:SetAttribute("MovementController", "ControllerManager")
    character:SetAttribute("VisualController", "AnimationController")
    CharacterStatsService.Initialize(character)

    local rig = CharacterRigService.Build(character, CharacterRigService.SpawnCFrame(player), template, row == nil)
    if not rig then
        character:Destroy()
        spawning[player] = nil
        return nil
    end

    character.Parent = Workspace
    CharacterRigService.Finish(rig)
    player.Character = character

    local hitboxes = EntityHitboxService.Attach(character, rig.visual)
    character:SetAttribute("CombatHitboxCount", hitboxes.count)

    pcall(function()
        rig.navigationRoot:SetNetworkOwner(player)
    end)

    character:GetAttributeChangedSignal("LifeState"):Connect(function()
        if character:GetAttribute("LifeState") ~= "Dead" then
            return
        end
        rig.controllerManager.MovingDirection = Vector3.zero
        rig.navigationRoot.AssemblyLinearVelocity = Vector3.zero
        rig.navigationRoot.AssemblyAngularVelocity = Vector3.zero
        pcall(function()
            rig.navigationRoot:SetNetworkOwner(nil)
        end)
        rig.navigationRoot.Anchored = true
        task.delay(3, function()
            if player.Parent == Players and player.Character == character then
                createCharacter(player)
            end
        end)
    end)

    character.Destroying:Connect(function()
        EntityHitboxService.Detach(character)
    end)

    spawning[player] = nil
    print(("[game1] character ready: %s · %s · asset %d · hitboxes %d · visual root %s")
        :format(
            player.Name,
            archetype,
            assetId,
            hitboxes.count,
            tostring(character:GetAttribute("VisualRootSource"))
        ))
    return character
end

function CharacterService.Respawn(player: Player): Model?
    if player.Parent ~= Players then
        return nil
    end
    return createCharacter(player)
end

function CharacterService.Start()
    if started then
        return
    end
    started = true
    Players.CharacterAutoLoads = false
    Players.PlayerAdded:Connect(function(player)
        task.defer(createCharacter, player)
    end)
    Players.PlayerRemoving:Connect(function(player)
        spawning[player] = nil
    end)
    for _, player in Players:GetPlayers() do
        task.defer(createCharacter, player)
    end
end

return table.freeze(CharacterService)
