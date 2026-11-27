local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local InsertService = game:GetService("InsertService")
local ServerStorage = game:GetService("ServerStorage")
local Workspace = game:GetService("Workspace")
local RunService = game:GetService("RunService")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CharacterShared = Shared:WaitForChild("character")
local CharacterMovementConfig = require(CharacterShared:WaitForChild("CharacterMovementConfig"))
local CharacterRegistry = require(CharacterShared:WaitForChild("CharacterRegistry"))

local CharacterCameraSync = require(script.Parent:WaitForChild("CharacterCameraSync"))
local CharacterCreationGateway = require(script.Parent:WaitForChild("CharacterCreationGateway"))
local CharacterCreationProfileStore = require(script.Parent:WaitForChild("CharacterCreationProfileStore"))
local CharacterCreationAppearanceService = require(script.Parent:WaitForChild("CharacterCreationAppearanceService"))
local CharacterCreationPreviewService = require(script.Parent:WaitForChild("CharacterCreationPreviewService"))
local CharacterCreationStreamingService = require(script.Parent:WaitForChild("CharacterCreationStreamingService"))
local GameOptions = require(Shared:WaitForChild("GameOptions"))
local CharacterRigService = require(script.Parent:WaitForChild("CharacterRigService"))
local VoidRecovery = require(script.Parent:WaitForChild("CharacterVoidRecovery"))
local CharacterAssemblyBuilder = require(script.Parent:WaitForChild("CharacterAssemblyBuilder"))
local CharacterStatsService = require(script.Parent:WaitForChild("CharacterStatsService"))
local Progression = require(script.Parent:WaitForChild("CharacterProgressionService"))
local GameplayTestLoadout = require(script.Parent.Parent:WaitForChild("dev"):WaitForChild("GameplayTestLoadout"))
local CombatRoot = script.Parent.Parent:WaitForChild("combat")
local EntityHitboxService = require(CombatRoot:WaitForChild("EntityHitboxService"))
local DeathLifecycleService = require(CombatRoot:WaitForChild("DeathLifecycleService"))
local WeaponEquipService = require(script.Parent.Parent:WaitForChild("weapon"):WaitForChild("WeaponEquipService"))

local CharacterService = {}
local started = false
local spawning: { [Player]: boolean } = {}
local deathContexts: { [Player]: any } = {}
local creationSelections: {[Player]: any} = {}
local createCharacter

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
    -- A published rig and resolved v2 recipe are the only supported spawn source.
    if not row or row.visualMode ~= "assembly" then
        return nil
    end
    local recipe = row.assembly
    if not recipe or recipe.schema_version ~= 2 or recipe.ready ~= true or type(recipe.rig) ~= "table" then
        return nil
    end
    return tonumber(recipe.rig.asset_id)
end

local function selectedCharacter(requestedOverride: string?): (any?, number?, string, string, string?, string?, string?)
    local requestedId = tostring(requestedOverride or "")
    if requestedId == "" then
        local configured = if RunService:IsStudio()
            then CharacterRegistry.studioAdminArchetypeId or CharacterRegistry.defaultArchetypeId
            else CharacterRegistry.defaultArchetypeId
        requestedId = tostring(configured or "")
    end
    local row = findArchetype(requestedId)
    local assetId = registeredAssetId(row)
    if row and assetId then
        return row, assetId, tostring(row.id), tostring(row.displayName or row.id),
            requestedId, tostring(row.race or ""), tostring(row.gender or "")
    end
    local reason = if requestedId == "" then "no default/admin v2 assembly selected"
        else "assembly not ready or unavailable: " .. requestedId
    warn("[game1] no character can spawn:", reason)
    return row, nil, requestedId, reason, requestedId, nil, nil
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

local function templateFor(row: any?, assetId: number): (Model?, string?)
    if not row or row.visualMode ~= "assembly" or not row.assembly then
        return nil, "v2 assembled character is required"
    end
    local cacheKey = "assembly-" .. tostring(row.assembly.fingerprint)
    local cached = cache:FindFirstChild(cacheKey)
    if cached and cached:IsA("Model") then return cached end
    local ok, result = pcall(CharacterAssemblyBuilder.Build, row.assembly, function(componentAssetId: number)
        return getAssetTemplate(componentAssetId, "component-" .. tostring(componentAssetId))
    end)
    if not ok then
        warn("[game1] character assembly failed", row.id, result)
        return nil, tostring(result)
    end
    local template = result :: Model
    template.Name = cacheKey
    template.Parent = cache
    return template
end

local function destroyPreviousCharacter(player: Player)
    local previous = player.Character
    if previous then
        EntityHitboxService.Detach(previous)
        player.Character = nil
        previous:Destroy()
    end
end

local function beginPlayerDeathIdle(player: Player)
    local context = deathContexts[player]
    if not context then
        return
    end
    local character = context.character
    if not character.Parent or player.Character ~= character or tostring(character:GetAttribute("LifeState") or "") ~= "Dying" then
        return
    end
    if character:GetAttribute("DeathIdleLifecycleStarted") == true then
        return
    end
    local lifecycleStarted = DeathLifecycleService.BeginDeathIdle(character, context.navigationRoot, context.visual, function(expiredCharacter: Model)
        -- Players stay at the terminal death pose above ground and do not
        -- auto-respawn; only Return to Town creates the replacement character.
        if player.Parent == Players and player.Character == expiredCharacter then
            deathContexts[player] = nil
            expiredCharacter:SetAttribute("ReturnToTownAvailable", true)
        end
    end, { sink = false })
    assert(lifecycleStarted, "DeathIdle lifecycle must start exactly once after the player terminal Death pose")
    character:SetAttribute("DeathIdleLifecycleStarted", true)
    character:SetAttribute("ReturnToTownAvailable", true)
end

createCharacter = function(player: Player, requestedArchetypeId: string?, reviveOnSpawn: boolean?, appearance: any?, spawnOverride: CFrame?): Model?
    if spawning[player] then
        return nil
    end
    spawning[player] = true

    local row, assetId, archetype, label, requestedArchetype, race, gender = selectedCharacter(requestedArchetypeId)
    if not assetId then
        player:SetAttribute("CharacterLoadError", "No ready v2 character: " .. tostring(label))
        spawning[player] = nil
        return nil
    end

    local template: Model?
    local loadError: string? = nil
    local temporaryTemplate = false
    local picked = appearance or creationSelections[player]
    if picked then
        local recipe, checked, problem = CharacterCreationAppearanceService.Resolve(archetype, picked)
        if not recipe then
            player:SetAttribute("CharacterLoadError", problem or "invalid appearance")
            spawning[player] = nil
            return nil
        end
        local ok, result = pcall(CharacterAssemblyBuilder.Build, recipe, function(componentAssetId: number)
            return getAssetTemplate(componentAssetId, "component-" .. tostring(componentAssetId))
        end)
        if not ok then loadError = tostring(result)
        else template = result; temporaryTemplate = true end
    else
        template, loadError = templateFor(row, assetId)
    end
    if not template then
        player:SetAttribute("CharacterLoadError", loadError or ("Cannot load character: " .. archetype))
        warn("[game1] character spawn cancelled; previous character preserved", archetype)
        spawning[player] = nil
        return nil
    end
    player:SetAttribute("CharacterLoadError", nil)

    destroyPreviousCharacter(player)

    local character = Instance.new("Model")
    character.Name = player.Name
    character:SetAttribute("CharacterArchetype", archetype)
    player:SetAttribute("SelectedCharacterArchetype", if archetype ~= "bootstrap" then archetype else "")
    character:SetAttribute("CharacterDisplayName", label)
    character:SetAttribute("CharacterRace", race or "")
    character:SetAttribute("CharacterGender", gender or "")
    character:SetAttribute("CharacterSkeletonSignature", if row and row.skeleton then tostring(row.skeleton.signature or "") else "")
    character:SetAttribute("AnimationProfileId", archetype)
    if row and row.assembly and row.assembly.rig then
        character:SetAttribute("CharacterRigAssetId", tostring(row.assembly.rig.asset_id))
        character:SetAttribute("CharacterRigRevision", row.assembly.rig.revision)
    end
    character:SetAttribute("AnimationWeaponSet", "hands")
    character:SetAttribute("RequestedCharacterArchetype", requestedArchetype or "")
    character:SetAttribute("UsingBootstrapVisual", archetype == "bootstrap")
    character:SetAttribute("CharacterOwnerUserId", player.UserId)
    character:SetAttribute("CustomCharacter", true)
    character:SetAttribute("AnimationMovementMode", "Run")
    character:SetAttribute("AnimationMovementDirection", "Forward")
    character:SetAttribute("MovementState", "Idle")
    character:SetAttribute("InCombat", false)
    character:SetAttribute("CombatState", "Peace")
    character:SetAttribute("CombatUntilServerTime", 0)
    character:SetAttribute("MovementController", "ControllerManager")
    character:SetAttribute("VisualController", "AnimationController")
    CharacterStatsService.Initialize(character, if row then row.stats else nil, Progression.LevelForPlayer(player))
    if reviveOnSpawn == true then
        -- Return-to-town spawns at full stats, but stays non-interactive until the
        -- owning client finishes the authored revive presentation. Movement, combat
        -- and monster targeting all already key off LifeState == Alive.
        character:SetAttribute("LifeState", "Reviving")
        character:SetAttribute("Damageable", false)
        character:SetAttribute("RevivePending", true)
    end

    GameplayTestLoadout.Mark(player, character)
    local testFrame = if GameplayTestLoadout.Get(player) then GameplayTestLoadout.Origin() else nil
    local rig = CharacterRigService.Build(character, testFrame or spawnOverride or CharacterRigService.SpawnCFrame(player), template, row == nil)
    if temporaryTemplate then template:Destroy() end
    if not rig then
        character:Destroy()
        spawning[player] = nil
        return nil
    end

    character.Parent = Workspace
    CharacterRigService.Finish(rig)
    player.Character = character
    Progression.Attach(player, character)
    if appearance then creationSelections[player] = appearance end
    require(script.Parent:WaitForChild("FaceEmotionService")).Bind(character)
    if GameplayTestLoadout.Get(player) then
        local ok, reason = GameplayTestLoadout.Apply(player, character)
        if not ok then warn("[game1][gameplay-test] " .. tostring(reason)) end
    else
        WeaponEquipService.EquipStartup(character)
    end

    local hitboxes = EntityHitboxService.Attach(character, rig.visual)
    character:SetAttribute("CombatHitboxCount", hitboxes.count)

    pcall(function()
        rig.navigationRoot:SetNetworkOwner(player)
    end)

    character:GetAttributeChangedSignal("LifeState"):Connect(function()
        if character:GetAttribute("LifeState") ~= "Dying" or character:GetAttribute("DeathPhysicsLocked") == true then
            return
        end
        character:SetAttribute("DeathPhysicsLocked", true)
        rig.controllerManager.MovingDirection = Vector3.zero
        rig.navigationRoot.AssemblyLinearVelocity = Vector3.zero
        rig.navigationRoot.AssemblyAngularVelocity = Vector3.zero
        pcall(function()
            rig.navigationRoot:SetNetworkOwner(nil)
        end)
        rig.navigationRoot.Anchored = true
        deathContexts[player] = {
            character = character,
            navigationRoot = rig.navigationRoot,
            visual = rig.visual,
        }

        -- The owning client evaluates Player.Character animation. It reports the
        -- single authoritative presentation edge: Death reached its final authored
        -- pose and is now frozen. Only then does the server start the 5s DeathIdle.
    end)

    character.Destroying:Connect(function()
        EntityHitboxService.Detach(character)
        DeathLifecycleService.Cancel(character)
        if deathContexts[player] and deathContexts[player].character == character then
            deathContexts[player] = nil
        end
    end)

    VoidRecovery.Watch(player, character, testFrame)
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

function CharacterService.IsAvailable(archetypeId: string): boolean
    local row = findArchetype(tostring(archetypeId or ""))
    return row ~= nil and registeredAssetId(row) ~= nil
end

function CharacterService.ListAvailable(): { any }
    local rows = {}
    for _, row in ipairs(CharacterRegistry.archetypes or {}) do
        if registeredAssetId(row) then
            table.insert(rows, row)
        end
    end
    return rows
end

function CharacterService.Respawn(player: Player, archetypeId: string?, spawnOverride: CFrame?): Model?
    if player.Parent ~= Players then
        return nil
    end
    -- Legacy Test Loadout and other spawn callers must not bypass the
    -- create -> select -> enter-world lifecycle when Character Creation is on.
    if GameOptions.CharacterCreationSettings().enabled == true
        and player:GetAttribute("CharacterCreationStatus") ~= "world" then
        return nil
    end
    local requested = tostring(archetypeId or "")
    if requested ~= "" and not CharacterService.IsAvailable(requested) then
        return nil
    end
    return createCharacter(player, requested, nil, nil, spawnOverride)
end

function CharacterService.ReturnToTown(player: Player): (boolean, string?)
    if player.Parent ~= Players then
        return false, "player unavailable"
    end
    local character = player.Character
    if not character or not character.Parent then
        return false, "character unavailable"
    end
    local lifeState = tostring(character:GetAttribute("LifeState") or "Alive")
    if lifeState ~= "DeathIdle" or character:GetAttribute("ReturnToTownAvailable") ~= true then
        return false, "return to town is only available after death animation"
    end
    local requested = tostring(player:GetAttribute("SelectedCharacterArchetype") or "")
    local restored = createCharacter(player, requested, true)
    if not restored then
        return false, "respawn failed"
    end
    return true, nil
end

local function finishRevive(player: Player)
    local character = player.Character
    if not character or not character.Parent then
        return
    end
    if tostring(character:GetAttribute("LifeState") or "") ~= "Reviving"
        or character:GetAttribute("RevivePending") ~= true
    then
        return
    end
    character:SetAttribute("RevivePending", false)
    character:SetAttribute("HP", math.max(0, tonumber(character:GetAttribute("MaxHP")) or 0))
    character:SetAttribute("Damageable", true)
    character:SetAttribute("LifeState", "Alive")
end

function CharacterService.Start()
    if started then
        return
    end
    started = true
    Players.CharacterAutoLoads = false
    Progression.Start()
    VoidRecovery.Start(function(player: Player)
        return player.Parent == Players and not spawning[player]
            and (GameOptions.CharacterCreationSettings().enabled ~= true
                or player:GetAttribute("CharacterCreationStatus") == "world")
    end, function(player: Player, fallen: Model)
        local archetype = tostring(fallen:GetAttribute("CharacterArchetype") or player:GetAttribute("SelectedCharacterArchetype") or "")
        local weapon = tostring(fallen:GetAttribute("EquippedWeaponSlug") or "")
        local isTest = GameplayTestLoadout.Get(player) ~= nil
        local replacement = CharacterService.Respawn(player, archetype)
        if not replacement then return false end
        if not isTest then
            -- Preserve the selected weapon; the test path reapplies its full transient loadout.
            if weapon == "" then WeaponEquipService.Unequip(replacement)
            elseif replacement:GetAttribute("EquippedWeaponSlug") ~= weapon then WeaponEquipService.Equip(replacement, weapon) end
        end
        print("[game1][void-recovery] restored " .. player.Name)
        return true
    end)

    local remotes = ReplicatedStorage:FindFirstChild("Game1Remotes") or Instance.new("Folder")
    remotes.Name = "Game1Remotes"
    remotes.Parent = ReplicatedStorage
    CharacterCameraSync.Start(remotes)
    local deathTerminalReached = remotes:FindFirstChild("DeathTerminalReached") or Instance.new("RemoteEvent")
    deathTerminalReached.Name = "DeathTerminalReached"
    deathTerminalReached.Parent = remotes
    deathTerminalReached.OnServerEvent:Connect(beginPlayerDeathIdle)

    local returnToTown = remotes:FindFirstChild("ReturnToTown") or Instance.new("RemoteFunction")
    returnToTown.Name = "ReturnToTown"
    returnToTown.Parent = remotes
    returnToTown.OnServerInvoke = function(player: Player)
        return CharacterService.ReturnToTown(player)
    end

    local reviveAnimationFinished = remotes:FindFirstChild("ReviveAnimationFinished") or Instance.new("RemoteEvent")
    reviveAnimationFinished.Name = "ReviveAnimationFinished"
    reviveAnimationFinished.Parent = remotes
    reviveAnimationFinished.OnServerEvent:Connect(finishRevive)

    local preview = CharacterCreationPreviewService.new(function(asset: number): Model?
        return getAssetTemplate(asset, "component-" .. tostring(asset))
    end)
    local creation = CharacterCreationGateway.new(
        GameOptions.CharacterCreationSettings().enabled == true,
        CharacterService.IsAvailable,
        function(player: Player, archetype: string, selected: any?, location: CFrame?): Model?
            return createCharacter(player, archetype, nil, selected, location)
        end,
        function(archetype: string, selection: any, savedProfile: boolean?): (any?, string?)
            local recipe, checked, reason = CharacterCreationAppearanceService.Resolve(archetype, selection, savedProfile)
            if not recipe then return nil, reason end
            return checked, nil
        end,
        CharacterCreationProfileStore,
        function(player: Player)
            destroyPreviousCharacter(player)
        end
    )
    CharacterCreationStreamingService.Start(GameOptions.CharacterCreationSettings())
    creation:Bind(remotes)
    if GameOptions.CharacterCreationSettings().enabled == true then
        preview:Bind(remotes)
        task.spawn(function()
            for _, id in ipairs({"human_male", "human_female"}) do
                local ready, failure = preview:Prepare(id, nil)
                if not ready then warn("[game1][character-creation] " .. id .. " preview: " .. tostring(failure)) end
            end
        end)
    end
    Players.PlayerAdded:Connect(function(player)
        creation:Join(player)
    end)
    Players.PlayerRemoving:Connect(function(player)
        if player:GetAttribute("CharacterCreationStatus") == "world" then
            CharacterCreationProfileStore.RememberPosition(player, player.Character)
        end
        creation:Leave(player)
        CharacterCreationProfileStore.ForgetSession(player)
        spawning[player] = nil
        deathContexts[player] = nil
        creationSelections[player] = nil
    end)
    for _, player in Players:GetPlayers() do
        creation:Join(player)
    end
    -- Studio and production server shutdowns can skip normal leave ordering.
    -- This is a bounded server-owned checkpoint, not a client-supplied position.
    game:BindToClose(function()
        for _, player in ipairs(Players:GetPlayers()) do
            if player:GetAttribute("CharacterCreationStatus") == "world" then
                CharacterCreationProfileStore.RememberPosition(player, player.Character)
            end
        end
    end)
end

return table.freeze(CharacterService)
