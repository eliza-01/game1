local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local ServerStorage = game:GetService("ServerStorage")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local MonsterShared = Shared:WaitForChild("monster")
local AnimationShared = Shared:WaitForChild("animation")
local AnimationSpeedScaling = require(AnimationShared:WaitForChild("AnimationSpeedScaling"))
local MonsterRegistry = require(MonsterShared:WaitForChild("MonsterRegistry"))
local MonsterAnimationRegistry = require(MonsterShared:WaitForChild("MonsterAnimationRegistry"))
local CombatRoot = script.Parent.Parent:WaitForChild("combat")
local EntityHitboxService = require(CombatRoot:WaitForChild("EntityHitboxService"))
local DeathLifecycleService = require(CombatRoot:WaitForChild("DeathLifecycleService"))
local SpawnRegistry = require(script.Parent:WaitForChild("MonsterSpawnRegistry"))

local MonsterRigBuilder = require(script.Parent:WaitForChild("MonsterRigBuilder"))
local MonsterSpawnGeometry = require(script.Parent:WaitForChild("MonsterSpawnGeometry"))
local MonsterAnimationTrackFactory = require(script.Parent:WaitForChild("MonsterAnimationTrackFactory"))
local MonsterInitialAttributes = require(script.Parent:WaitForChild("MonsterInitialAttributes"))
local MonsterWanderController = require(script.Parent:WaitForChild("MonsterWanderController"))
local MonsterDeathLifecycle = require(script.Parent:WaitForChild("MonsterDeathLifecycle"))
local MonsterSpawnerService = {}
local started = false
local spawnRandom = Random.new()
local states = {}
local monstersFolder: Folder? = nil

local function finite(value: any, fallback: number): number
    local number = tonumber(value)
    if number == nil or number ~= number or number == math.huge or number == -math.huge then
        return fallback
    end
    return number
end

local function ensureMonstersFolder(): Folder
    local existing = Workspace:FindFirstChild("Monsters")
    if existing and not existing:IsA("Folder") then
        error("Workspace.Monsters exists but is not a Folder")
    end
    if not existing then
        existing = Instance.new("Folder")
        existing.Name = "Monsters"
        existing.Parent = Workspace
    end
    monstersFolder = existing :: Folder
    return monstersFolder
end

local spawnGeometry = MonsterSpawnGeometry.new(spawnRandom, ensureMonstersFolder)

local function resolvePath(path: string): Instance?
    local parts = string.split(path, ".")
    local current: Instance? = nil
    for index, segment in ipairs(parts) do
        if index == 1 then
            if segment ~= "ServerStorage" then
                return nil
            end
            current = ServerStorage
        else
            current = current and current:FindFirstChild(segment) or nil
            if not current then
                return nil
            end
        end
    end
    return current
end

local function monsterDefinition(slug: string): any?
    local monsters = MonsterRegistry.monsters
    return monsters and monsters[slug] or nil
end

local function playTrackAtConfiguredSpeed(model: Model, track: AnimationTrack?, channel: string, fadeTime: number)
    if not track then
        return
    end
    local percent = AnimationSpeedScaling.ResolveForAnimation(model, channel, track.Animation and track.Animation.AnimationId)
    model:SetAttribute("AnimationPlaybackSpeedPercent", percent)
    local speed = percent / 100
    if track.IsPlaying then
        track:AdjustSpeed(speed)
    else
        track:Play(fadeTime, 1, speed)
    end
end

local function stopTrack(track: AnimationTrack?)
    if not track then
        return
    end
    pcall(function()
        track:Stop(0.08)
    end)
end

local function weightedIdleChoice(choices: {any}): any?
    local total = 0
    for _, choice in ipairs(choices) do
        total += math.max(1, finite(choice.row and choice.row.weight, 100))
    end
    if total <= 0 then
        return nil
    end
    local roll = spawnRandom:NextNumber(0, total)
    local cursor = 0
    for _, choice in ipairs(choices) do
        cursor += math.max(1, finite(choice.row and choice.row.weight, 100))
        if roll <= cursor then
            return choice
        end
    end
    return choices[#choices]
end

local function stopIdleState(entry: any)
    stopTrack(entry.idleTrack)
    for _, choice in ipairs(entry.idleChoices or {}) do
        if choice.role == "special" then
            stopTrack(choice.track)
        end
    end
    entry.activeIdleSpecial = nil
end

local function playBaseIdle(model: Model, entry: any)
    if entry.dying or model:GetAttribute("MonsterCombatActive") == true or model:GetAttribute("InCombat") == true then
        return
    end
    stopTrack(entry.walkTrack)
    stopTrack(entry.runTrack)
    model:SetAttribute("MonsterAnimationState", "idle")
    model:SetAttribute("MonsterIdleVariant", "base")
    if entry.idleTrack then
        pcall(function()
            playTrackAtConfiguredSpeed(model, entry.idleTrack, "idle", 0.12)
        end)
    end
end

local function playCombatIdleState(model: Model, entry: any)
    if entry.dying or model:GetAttribute("MonsterCombatActive") == true then
        return
    end
    stopIdleState(entry)
    stopTrack(entry.walkTrack)
    stopTrack(entry.runTrack)
    model:SetAttribute("MonsterAnimationState", "combat_idle")
    model:SetAttribute("MonsterIdleVariant", "combat")
    if entry.combatIdleTrack then
        pcall(function()
            playTrackAtConfiguredSpeed(model, entry.combatIdleTrack, "combat_idle", 0.1)
        end)
    end
end

local wanderController = MonsterWanderController.new(spawnRandom, spawnGeometry, {
    stopTrack = stopTrack,
    stopIdleState = stopIdleState,
    playBaseIdle = playBaseIdle,
    playCombatIdleState = playCombatIdleState,
    playTrackAtConfiguredSpeed = playTrackAtConfiguredSpeed,
})

local function maybePlayIdleSpecial(model: Model, entry: any)
    if entry.dying or entry.wandering or entry.activeIdleSpecial ~= nil
        or model:GetAttribute("InCombat") == true or model:GetAttribute("MonsterCombatActive") == true then
        return
    end
    local choice = weightedIdleChoice(entry.idleChoices or {})
    if not choice or choice.role ~= "special" then
        return
    end
    entry.activeIdleSpecial = choice
    stopTrack(entry.idleTrack)
    model:SetAttribute("MonsterAnimationState", "idle")
    model:SetAttribute("MonsterIdleVariant", ("special_%02d"):format(math.max(1, math.floor(finite(choice.row.variant, 1)))))
    local ok = pcall(function()
        playTrackAtConfiguredSpeed(model, choice.track, "idle", 0.08)
    end)
    if not ok then
        entry.activeIdleSpecial = nil
        playBaseIdle(model, entry)
    end
end

local function releaseInstance(state: any, model: Model, scheduleRespawn: boolean, externallyDestroying: boolean?)
    local entry = state.instances[model]
    if entry == nil then
        return
    end
    state.instances[model] = nil
    DeathLifecycleService.Cancel(model)
    wanderController:Dispose(entry)
    for _, connection in ipairs(entry.connections or {}) do
        connection:Disconnect()
    end
    table.clear(entry.connections or {})
    stopIdleState(entry)
    stopTrack(entry.combatIdleTrack)
    stopTrack(entry.deathTrack)
    if externallyDestroying then
        -- Deferred Destroying signals can run after the instance is locked.
        -- Detach removes its hitbox binding first; remaining attribute writes are best effort.
        pcall(EntityHitboxService.Detach, model)
    else
        EntityHitboxService.Detach(model)
    end
    if model.Parent and not externallyDestroying then
        model:Destroy()
    end
    if scheduleRespawn and state.enabled then
        local delaySeconds = math.max(0, finite(state.record.respawnSeconds, 10))
        task.delay(delaySeconds, function()
            if state.enabled then
                state.fill()
            end
        end)
    end
end

local deathLifecycle = MonsterDeathLifecycle.new({
    stopWanderMovement = function(entry: any) wanderController:Stop(entry) end,
    stopIdleState = stopIdleState,
    stopTrack = stopTrack,
    releaseInstance = releaseInstance,
})

local function watch(entry: any, signal: RBXScriptSignal, callback: (...any) -> ())
    local connection = signal:Connect(callback)
    table.insert(entry.connections, connection)
end

local function spawnOne(state: any): Model?
    local record = state.record
    local slug = tostring(record.monsterSlug or "")
    local definition = monsterDefinition(slug)
    if not definition then
        warn("[game1][monster-spawn] unknown monster slug in runtime registry: " .. slug)
        return nil
    end
    if tostring(definition.status or "") ~= "PUBLISHED" then
        warn("[game1][monster-spawn] monster is not published: " .. slug)
        return nil
    end
    local template = resolvePath(tostring(definition.serverStoragePath or ""))
    if not template or not template:IsA("Model") then
        warn("[game1][monster-spawn] Studio template missing for " .. slug .. " at " .. tostring(definition.serverStoragePath))
        return nil
    end

    local model = template:Clone()
    local instanceId = tostring(record.spawnId or "spawn") .. "-" .. tostring(math.floor(os.clock() * 1000)) .. "-" .. tostring(spawnRandom:NextInteger(1000, 9999))
    model.Name = slug .. "_" .. instanceId:sub(-4)
    model.Parent = ensureMonstersFolder()
    local visual, visualRoot = MonsterRigBuilder.PrepareVisual(model)
    if not visualRoot then
        model:Destroy()
        warn("[game1][monster-spawn] monster contains no usable BasePart: " .. slug)
        return nil
    end
    local animationRootBridgeCount = MonsterRigBuilder.EnsureRuntimeAnimationRoot(visual)
    model:SetAttribute("RuntimeAnimationRootBridgeCount", animationRootBridgeCount)
    local surface = spawnGeometry:RandomSpawnPoint(record)
    local yaw = spawnRandom:NextNumber(0, math.pi * 2)
    MonsterRigBuilder.GroundAlign(model, surface, yaw)
    MonsterInitialAttributes.Apply(model, definition, record, instanceId)
    local navigationRoot, humanoid = MonsterRigBuilder.CreateNavigationRig(model, visual, visualRoot, surface, yaw)
    if not navigationRoot or not humanoid then
        model:Destroy()
        warn("[game1][monster-spawn] monster navigation rig could not be created: " .. slug)
        return nil
    end
    local hitbox = EntityHitboxService.Attach(model, visual)
    model:SetAttribute("CombatHitboxCount", hitbox.count)

    local entry = MonsterAnimationTrackFactory.Load(
        MonsterAnimationRegistry.profiles and MonsterAnimationRegistry.profiles[slug], model, visual
    )
    entry.visual = visual
    entry.navigationRoot = navigationRoot
    entry.humanoid = humanoid
    entry.wandering = false
    entry.dying = false
    entry.deathPoseHeld = false
    entry.connections = {}
    local idleTrack = entry.idleTrack
    local idleChoices = entry.idleChoices
    state.instances[model] = entry

    for _, choice in ipairs(idleChoices) do
        if choice.role == "special" then
            watch(entry, choice.track.Ended, function()
                if state.instances[model] ~= entry or entry.dying or entry.activeIdleSpecial ~= choice then
                    return
                end
                entry.activeIdleSpecial = nil
                playBaseIdle(model, entry)
            end)
        end
    end
    if idleTrack then
        watch(entry, idleTrack.DidLoop, function()
            if state.instances[model] == entry then
                maybePlayIdleSpecial(model, entry)
            end
        end)
    end
    playBaseIdle(model, entry)
    wanderController:Start(state, model, entry)

    watch(entry, model:GetAttributeChangedSignal("MonsterCombatActive"), function()
        if state.instances[model] ~= entry or entry.dying then
            return
        end
        if model:GetAttribute("MonsterCombatActive") == true then
            wanderController:Stop(entry)
            stopIdleState(entry)
            stopTrack(entry.combatIdleTrack)
            model:SetAttribute("MonsterIdleVariant", nil)
        else
            wanderController:Stop(entry)
            if model:GetAttribute("InCombat") == true then
                playCombatIdleState(model, entry)
            else
                playBaseIdle(model, entry)
            end
        end
    end)

    watch(entry, model:GetAttributeChangedSignal("InCombat"), function()
        if state.instances[model] ~= entry or entry.dying or model:GetAttribute("MonsterCombatActive") == true then
            return
        end
        wanderController:Stop(entry)
        if model:GetAttribute("InCombat") == true then
            playCombatIdleState(model, entry)
        else
            stopTrack(entry.combatIdleTrack)
            playBaseIdle(model, entry)
        end
    end)

    watch(entry, model:GetAttributeChangedSignal("RunSpeed"), function()
        if state.instances[model] == entry then
            wanderController:Refresh(model, entry)
        end
    end)
    watch(entry, model:GetAttributeChangedSignal("MonsterLocomotionMode"), function()
        if state.instances[model] == entry then
            wanderController:Refresh(model, entry)
        end
    end)
    for _, channel in ipairs({ "run", "walk" }) do
        watch(entry, model:GetAttributeChangedSignal(AnimationSpeedScaling.DebugUnitsPerPercentAttribute(channel)), function()
            if state.instances[model] == entry then
                wanderController:Refresh(model, entry)
            end
        end)
    end
    watch(entry, model:GetAttributeChangedSignal("LifeState"), function()
        if state.instances[model] ~= entry then
            return
        end
        if tostring(model:GetAttribute("LifeState") or "") == "Dying" then
            deathLifecycle:Begin(state, model, entry)
        end
    end)
    watch(entry, model.Destroying, function()
        -- External Model:Destroy must release connections, tracks and hitbox too.
        if state.instances[model] == entry then
            releaseInstance(state, model, false, true)
        end
    end)
    return model
end

local function stateFill(state: any)
    if not state.enabled then
        return
    end
    local target = math.max(1, math.floor(finite(state.record.maxAlive, 1)))
    local alive = 0
    for model in pairs(state.instances) do
        -- Dying/DeathIdle still occupies its spawn slot until the corpse is fully
        -- underground and released. Do not spawn a replacement on the HP=0 frame.
        if model.Parent then
            alive += 1
        end
    end
    while alive < target do
        local model = spawnOne(state)
        if not model then
            break
        end
        alive += 1
    end
end

local function recordAppliesHere(record: any): boolean
    if record.enabled == false then
        return false
    end
    local placeId = math.floor(finite(record.placeId, 0))
    return placeId == 0 or game.PlaceId == 0 or placeId == game.PlaceId
end

local function removeAuthoringVisualsFromSimulation()
    local authoring = Workspace:FindFirstChild("Game1Authoring")
    if not authoring then
        return
    end
    local monsterSpawns = authoring:FindFirstChild("MonsterSpawns")
    if monsterSpawns then
        -- Spawn circles, marker arrows and BillboardGui IDs are editor authoring aids.
        -- The Play/Run DataModel uses the generated registry and must not render them.
        monsterSpawns:Destroy()
    end
    if #authoring:GetChildren() == 0 then
        authoring:Destroy()
    end
end

function MonsterSpawnerService.Start()
    if started then
        return
    end
    started = true
    removeAuthoringVisualsFromSimulation()
    ensureMonstersFolder()

    -- Death runs as a normal one-shot. PreAnimation only catches the step that
    -- would reach/pass AnimationTrack.Length and freezes the already-evaluated
    -- visible pose. DeathIdle must never seek into a terminal reset sample.
    RunService.PreAnimation:Connect(function(deltaTimeSim)
        for _, state in pairs(states) do
            for model, entry in pairs(state.instances) do
                deathLifecycle:Maintain(state, model, entry, deltaTimeSim)
            end
        end
    end)

    local count = 0
    for _, record in ipairs(SpawnRegistry.records or {}) do
        if recordAppliesHere(record) then
            local state = {
                record = record,
                enabled = true,
                instances = {},
            }
            state.fill = function()
                stateFill(state)
            end
            states[tostring(record.spawnId or count + 1)] = state
            stateFill(state)
            count += 1
        end
    end
    print(("[game1][monster-spawn] %d authored spawn(s) active"):format(count))
end

return table.freeze(MonsterSpawnerService)
