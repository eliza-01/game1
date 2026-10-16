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

local MonsterRigBuilder = require(script.Parent:WaitForChild("MonsterRigBuilder"))
local MonsterSpawnGeometry = require(script.Parent:WaitForChild("MonsterSpawnGeometry"))
local MonsterAnimationTrackFactory = require(script.Parent:WaitForChild("MonsterAnimationTrackFactory"))
local MonsterInitialAttributes = require(script.Parent:WaitForChild("MonsterInitialAttributes"))
local MonsterWanderController = require(script.Parent:WaitForChild("MonsterWanderController"))
local MonsterDeathLifecycle = require(script.Parent:WaitForChild("MonsterDeathLifecycle"))
local MonsterIdlePresentation = require(script.Parent:WaitForChild("MonsterIdlePresentation"))
local MonsterPopulationController = require(script.Parent:WaitForChild("MonsterPopulationController"))
local MonsterSpawnPresentation = require(script.Parent:WaitForChild("MonsterSpawnPresentation"))
local MonsterSpawnerService = {}
local started = false
local spawnRandom = Random.new()
local monstersFolder: Folder? = nil

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

-- The same RNG is shared with spawn geometry and wander. Presentation consumes it
-- only on idle loop events, preserving M90/M91 random-draw ordering.
local population: any -- Initialized after spawnOne; release callbacks share the same population.
local idlePresentation = MonsterIdlePresentation.new(spawnRandom)
local wanderController = MonsterWanderController.new(spawnRandom, spawnGeometry, idlePresentation)

local function releaseInstance(state: any, model: Model, scheduleRespawn: boolean, externallyDestroying: boolean?)
    local entry = state.instances[model]
    if entry == nil then
        return
    end
    population:UnregisterInstance(state, model)
    DeathLifecycleService.Cancel(model)
    if entry.spawnPresentation then
        entry.spawnPresentation:Cancel()
    end
    wanderController:Dispose(entry)
    for _, connection in ipairs(entry.connections or {}) do
        connection:Disconnect()
    end
    table.clear(entry.connections or {})
    idlePresentation.stopIdleState(entry)
    idlePresentation.stopTrack(entry.combatIdleTrack)
    idlePresentation.stopTrack(entry.deathTrack)
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
    if scheduleRespawn then
        population:ScheduleRespawn(state, entry.diedAt)
    end
end

local deathLifecycle = MonsterDeathLifecycle.new({
    stopWanderMovement = function(entry: any) wanderController:Stop(entry) end,
    stopIdleState = idlePresentation.stopIdleState,
    stopTrack = idlePresentation.stopTrack,
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
    local riseFromGround = definition.behavior and definition.behavior.riseFromGround == true
    local spawnPresentation = MonsterSpawnPresentation.Prepare(model, visual, navigationRoot, humanoid, riseFromGround)
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
    entry.spawnPresentation = spawnPresentation
    population:RegisterInstance(state, model, entry)

    -- Presentation owns idle clip callbacks; the instance still owns/disconnects
    -- the underlying RBXScriptConnections through the M91 watch registry.
    idlePresentation.BindIdleEvents(model, entry, function(signal, callback)
        watch(entry, signal, callback)
    end, function()
        return state.instances[model] == entry
    end)
    idlePresentation.playBaseIdle(model, entry)
    spawnPresentation:Start(function()
        if state.instances[model] == entry and not entry.dying then
            wanderController:Start(state, model, entry)
        end
    end)

    watch(entry, model:GetAttributeChangedSignal("MonsterCombatActive"), function()
        if state.instances[model] ~= entry or entry.dying then
            return
        end
        if model:GetAttribute("MonsterCombatActive") == true then
            wanderController:Stop(entry)
            idlePresentation.stopIdleState(entry)
            idlePresentation.stopTrack(entry.combatIdleTrack)
            model:SetAttribute("MonsterIdleVariant", nil)
        else
            wanderController:Stop(entry)
            if model:GetAttribute("InCombat") == true then
                idlePresentation.playCombatIdleState(model, entry)
            else
                idlePresentation.playBaseIdle(model, entry)
            end
        end
    end)

    watch(entry, model:GetAttributeChangedSignal("InCombat"), function()
        if state.instances[model] ~= entry or entry.dying or model:GetAttribute("MonsterCombatActive") == true then
            return
        end
        wanderController:Stop(entry)
        if model:GetAttribute("InCombat") == true then
            idlePresentation.playCombatIdleState(model, entry)
        else
            idlePresentation.stopTrack(entry.combatIdleTrack)
            idlePresentation.playBaseIdle(model, entry)
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
            entry.diedAt = os.clock()
            spawnPresentation:Cancel()
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

-- Population owns spawn records, live slots, maxAlive and delayed respawns.
-- The callback is injected to keep instance construction and presentation in Spawner.
population = MonsterPopulationController.new(spawnOne)

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
        for _, state in pairs(population:States()) do
            for model, entry in pairs(state.instances) do
                deathLifecycle:Maintain(state, model, entry, deltaTimeSim)
            end
        end
    end)

    local count = population:Start()
    print(("[game1][monster-spawn] %d authored spawn(s) active"):format(count))
end

return table.freeze(MonsterSpawnerService)
