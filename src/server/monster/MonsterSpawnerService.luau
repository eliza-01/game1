local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local ServerStorage = game:GetService("ServerStorage")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local MonsterShared = Shared:WaitForChild("monster")
local CharacterShared = Shared:WaitForChild("character")
local AnimationShared = Shared:WaitForChild("animation")
local CharacterMovementConfig = require(CharacterShared:WaitForChild("CharacterMovementConfig"))
local AnimationSpeedScaling = require(AnimationShared:WaitForChild("AnimationSpeedScaling"))
local MonsterRegistry = require(MonsterShared:WaitForChild("MonsterRegistry"))
local MonsterAnimationRegistry = require(MonsterShared:WaitForChild("MonsterAnimationRegistry"))
local CombatRoot = script.Parent.Parent:WaitForChild("combat")
local EntityHitboxService = require(CombatRoot:WaitForChild("EntityHitboxService"))
local DeathLifecycleService = require(CombatRoot:WaitForChild("DeathLifecycleService"))
local DeathAnimationPolicy = require(Shared:WaitForChild("combat"):WaitForChild("DeathAnimationPolicy"))
local SpawnRegistry = require(script.Parent:WaitForChild("MonsterSpawnRegistry"))

local MonsterRigBuilder = require(script.Parent:WaitForChild("MonsterRigBuilder"))
local MonsterSpawnGeometry = require(script.Parent:WaitForChild("MonsterSpawnGeometry"))
local MonsterAnimationTrackFactory = require(script.Parent:WaitForChild("MonsterAnimationTrackFactory"))
local MonsterInitialAttributes = require(script.Parent:WaitForChild("MonsterInitialAttributes"))
local MonsterSpawnerService = {}
local started = false
local spawnRandom = Random.new()
local states = {}
local monstersFolder: Folder? = nil

local WANDER_PAUSE_MIN_SECONDS = 3
local WANDER_PAUSE_MAX_SECONDS = 10
local WANDER_MOVE_REFRESH_SECONDS = 1
local WANDER_ARRIVAL_TOLERANCE = 1.25

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

local function monsterLocomotionMode(model: Model): string
    return string.lower(tostring(model:GetAttribute("MonsterLocomotionMode") or "Walk")) == "run" and "Run" or "Walk"
end

local function locomotionSpeedFor(model: Model): number
    return CharacterMovementConfig.RobloxSpeed(nil, model:GetAttribute("RunSpeed"), monsterLocomotionMode(model))
end

local function locomotionTrackFor(entry: any, mode: string): AnimationTrack?
    if mode == "Run" then
        return entry.runTrack or entry.walkTrack
    end
    return entry.walkTrack or entry.runTrack
end

local function refreshWanderLocomotion(model: Model, entry: any)
    if not entry.wandering or entry.dying or model:GetAttribute("MonsterCombatActive") == true or model:GetAttribute("InCombat") == true then
        return
    end
    local humanoid = entry.humanoid
    local navigationRoot = entry.navigationRoot
    if not humanoid or not humanoid.Parent or not navigationRoot or not navigationRoot.Parent then
        return
    end

    local mode = monsterLocomotionMode(model)
    local activeTrack = locomotionTrackFor(entry, mode)
    local inactiveTrack = mode == "Run" and entry.walkTrack or entry.runTrack
    if inactiveTrack and inactiveTrack ~= activeTrack then
        stopTrack(inactiveTrack)
    end
    if activeTrack then
        pcall(function() playTrackAtConfiguredSpeed(model, activeTrack, string.lower(mode), 0.1) end)
    end
    model:SetAttribute("MonsterAnimationState", string.lower(mode))

    local speed = math.max(0, locomotionSpeedFor(model))
    humanoid.WalkSpeed = speed
    humanoid.AutoRotate = true
    local destination = entry.wanderDestination
    if destination then
        if speed <= 0.001 then
            entry.wanderDeadline = math.huge
        else
            local remaining = MonsterSpawnGeometry.HorizontalDistance(navigationRoot.Position, destination)
            entry.wanderDeadline = os.clock() + math.max(8, remaining / speed + 4)
        end
        humanoid:MoveTo(destination)
    end
end

local function stopWanderMovement(entry: any)
    entry.wandering = false
    entry.wanderDestination = nil
    entry.wanderDeadline = nil
    stopTrack(entry.walkTrack)
    stopTrack(entry.runTrack)
    local humanoid = entry.humanoid
    local navigationRoot = entry.navigationRoot
    if humanoid and navigationRoot and navigationRoot.Parent then
        humanoid.WalkSpeed = 0
        humanoid.AutoRotate = false
        humanoid:Move(Vector3.zero, false)
        humanoid:MoveTo(navigationRoot.Position)
    end
end

local function startWanderLoop(state: any, model: Model, entry: any)
    local radius = math.max(0, finite(state.record.spawnRadius, 0))
    if radius <= 0 or not entry.humanoid or not entry.navigationRoot then
        model:SetAttribute("MonsterWanderEnabled", false)
        return
    end
    model:SetAttribute("MonsterWanderEnabled", true)
    task.spawn(function()
        task.wait(spawnRandom:NextNumber(0.35, 1.35))
        while state.instances[model] == entry and model.Parent and not entry.dying do
            task.wait(spawnRandom:NextNumber(WANDER_PAUSE_MIN_SECONDS, WANDER_PAUSE_MAX_SECONDS))
            if state.instances[model] ~= entry or not model.Parent or entry.dying then
                break
            end
            if model:GetAttribute("MonsterCombatActive") == true or model:GetAttribute("InCombat") == true then
                continue
            end

            local navigationRoot = entry.navigationRoot
            local humanoid = entry.humanoid
            if not navigationRoot or not navigationRoot.Parent or not humanoid or not humanoid.Parent then
                break
            end
            local destination, routeLength, outsideSpawn = spawnGeometry:ChooseWanderTarget(state.record, navigationRoot.Position)
            if not destination or routeLength <= WANDER_ARRIVAL_TOLERANCE then
                continue
            end

            stopIdleState(entry)
            entry.wandering = true
            entry.wanderDestination = destination
            model:SetAttribute("MonsterIdleVariant", nil)
            model:SetAttribute("MonsterWanderTargetX", destination.X)
            model:SetAttribute("MonsterWanderTargetZ", destination.Z)
            model:SetAttribute("MonsterWanderRouteLength", routeLength)
            model:SetAttribute("MonsterWanderOutsideSpawn", outsideSpawn)
            refreshWanderLocomotion(model, entry)

            local finished = false
            local moveConnection = humanoid.MoveToFinished:Connect(function()
                finished = true
            end)
            local nextRefresh = os.clock() + WANDER_MOVE_REFRESH_SECONDS
            while not finished
                and state.instances[model] == entry
                and model.Parent
                and not entry.dying
                and model:GetAttribute("MonsterCombatActive") ~= true
                and model:GetAttribute("InCombat") ~= true
                and os.clock() < (entry.wanderDeadline or math.huge)
            do
                task.wait(0.1)
                if MonsterSpawnGeometry.HorizontalDistance(navigationRoot.Position, destination) <= WANDER_ARRIVAL_TOLERANCE then
                    finished = true
                    break
                end
                if os.clock() >= nextRefresh then
                    nextRefresh = os.clock() + WANDER_MOVE_REFRESH_SECONDS
                    -- Same destination is reissued before Humanoid's internal MoveTo timeout.
                    -- Roblox physics owns the continuous motion; game1 never CFrames the monster per frame.
                    humanoid:MoveTo(destination)
                end
            end
            moveConnection:Disconnect()

            if state.instances[model] == entry and model.Parent and not entry.dying then
                stopWanderMovement(entry)
                model:SetAttribute("MonsterWanderRouteLength", 0)
                if model:GetAttribute("MonsterCombatActive") ~= true then
                    if model:GetAttribute("InCombat") == true then
                        playCombatIdleState(model, entry)
                    else
                        playBaseIdle(model, entry)
                    end
                end
            end
        end
    end)
end

local function releaseInstance(state: any, model: Model, scheduleRespawn: boolean)
    local entry = state.instances[model]
    if entry == nil then
        return
    end
    state.instances[model] = nil
    DeathLifecycleService.Cancel(model)
    stopWanderMovement(entry)
    stopIdleState(entry)
    stopTrack(entry.combatIdleTrack)
    stopTrack(entry.deathTrack)
    EntityHitboxService.Detach(model)
    if model.Parent then
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

local function enterDeathIdle(state: any, model: Model, entry: any)
    if entry.deathPoseHeld or state.instances[model] ~= entry or not model.Parent then
        return
    end
    entry.deathPoseHeld = true
    model:SetAttribute("MonsterAnimationState", "death_idle")
    model:SetAttribute("DeathTerminalPoseHeld", true)
    model:SetAttribute("DeathTerminalPoseHeldAt", os.clock())
    local started = DeathLifecycleService.BeginDeathIdle(model, entry.navigationRoot, entry.visual, function()
        releaseInstance(state, model, true)
    end)
    assert(started, "DeathIdle lifecycle must start exactly once after the terminal Death pose")
end

local function maintainDeathTerminalPose(state: any, model: Model, entry: any, deltaTimeSim: number)
    if not entry.dying
        or entry.deathPoseHeld
        or state.instances[model] ~= entry
        or not model.Parent
        or tostring(model:GetAttribute("LifeState") or "") ~= "Dying"
    then
        return
    end

    local track = entry.deathTrack
    if not track then
        return
    end

    local reached, terminalTime = DeathAnimationPolicy.LatchVisibleTerminalPose(track, deltaTimeSim)
    if not reached then
        return
    end

    model:SetAttribute("DeathAnimationLength", track.Length)
    model:SetAttribute("DeathAnimationTerminalTime", terminalTime)
    enterDeathIdle(state, model, entry)
end

local function beginDeath(state: any, model: Model, entry: any)
    if entry.dying then
        return
    end
    entry.dying = true
    entry.deathPoseHeld = false
    model:SetAttribute("Damageable", false)
    model:SetAttribute("MonsterAnimationState", "death")
    model:SetAttribute("MonsterIdleVariant", nil)
    model:SetAttribute("DeathAnimationStartedAt", os.clock())
    model:SetAttribute("DeathTerminalPoseHeld", false)
    stopWanderMovement(entry)
    stopIdleState(entry)
    stopTrack(entry.combatIdleTrack)
    if entry.navigationRoot and entry.navigationRoot.Parent then
        entry.navigationRoot.AssemblyLinearVelocity = Vector3.zero
        entry.navigationRoot.AssemblyAngularVelocity = Vector3.zero
        entry.navigationRoot.Anchored = true
    end

    local track = entry.deathTrack
    if not track then
        warn("[game1][monster-spawn] required death animation track is missing; monster remains Dying")
        return
    end
    model:SetAttribute("AnimationPlaybackSpeedPercent", AnimationSpeedScaling.ResolveForAnimation(model, "death", track.Animation and track.Animation.AnimationId))
    DeathAnimationPolicy.Start(track, AnimationSpeedScaling.ResolveScaleForAnimation(model, "death", track.Animation and track.Animation.AnimationId))
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
    local idleTrack = entry.idleTrack
    local idleChoices = entry.idleChoices
    state.instances[model] = entry

    for _, choice in ipairs(idleChoices) do
        if choice.role == "special" then
            choice.track.Ended:Connect(function()
                if state.instances[model] ~= entry or entry.dying or entry.activeIdleSpecial ~= choice then
                    return
                end
                entry.activeIdleSpecial = nil
                playBaseIdle(model, entry)
            end)
        end
    end
    if idleTrack then
        idleTrack.DidLoop:Connect(function()
            if state.instances[model] == entry then
                maybePlayIdleSpecial(model, entry)
            end
        end)
    end
    playBaseIdle(model, entry)
    startWanderLoop(state, model, entry)

    model:GetAttributeChangedSignal("MonsterCombatActive"):Connect(function()
        if state.instances[model] ~= entry or entry.dying then
            return
        end
        if model:GetAttribute("MonsterCombatActive") == true then
            stopWanderMovement(entry)
            stopIdleState(entry)
            stopTrack(entry.combatIdleTrack)
            model:SetAttribute("MonsterIdleVariant", nil)
        else
            stopWanderMovement(entry)
            if model:GetAttribute("InCombat") == true then
                playCombatIdleState(model, entry)
            else
                playBaseIdle(model, entry)
            end
        end
    end)

    model:GetAttributeChangedSignal("InCombat"):Connect(function()
        if state.instances[model] ~= entry or entry.dying or model:GetAttribute("MonsterCombatActive") == true then
            return
        end
        stopWanderMovement(entry)
        if model:GetAttribute("InCombat") == true then
            playCombatIdleState(model, entry)
        else
            stopTrack(entry.combatIdleTrack)
            playBaseIdle(model, entry)
        end
    end)

    model:GetAttributeChangedSignal("RunSpeed"):Connect(function()
        if state.instances[model] == entry then
            refreshWanderLocomotion(model, entry)
        end
    end)
    model:GetAttributeChangedSignal("MonsterLocomotionMode"):Connect(function()
        if state.instances[model] == entry then
            refreshWanderLocomotion(model, entry)
        end
    end)
    for _, channel in ipairs({ "run", "walk" }) do
        model:GetAttributeChangedSignal(AnimationSpeedScaling.DebugUnitsPerPercentAttribute(channel)):Connect(function()
            if state.instances[model] == entry then
                refreshWanderLocomotion(model, entry)
            end
        end)
    end
    model:GetAttributeChangedSignal("LifeState"):Connect(function()
        if state.instances[model] ~= entry then
            return
        end
        if tostring(model:GetAttribute("LifeState") or "") == "Dying" then
            beginDeath(state, model, entry)
        end
    end)
    model.Destroying:Connect(function()
        if state.instances[model] == entry then
            state.instances[model] = nil
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
                maintainDeathTerminalPose(state, model, entry, deltaTimeSim)
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
