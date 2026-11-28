local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local ServerStorage = game:GetService("ServerStorage")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local MonsterShared = Shared:WaitForChild("monster")
local MonsterRegistry = require(MonsterShared:WaitForChild("MonsterRegistry"))
local MonsterAnimationRegistry = require(MonsterShared:WaitForChild("MonsterAnimationRegistry"))
local CombatRoot = script.Parent.Parent:WaitForChild("combat")
local EntityHitboxService = require(CombatRoot:WaitForChild("EntityHitboxService"))
local DeathLifecycleService = require(CombatRoot:WaitForChild("DeathLifecycleService"))

local MnpcLifecycle = require(script.Parent.Parent:WaitForChild("actor"):WaitForChild("MnpcEntityLifecycle"))
local Demand = require(script.Parent.Parent:WaitForChild("actor"):WaitForChild("MnpcDemandLifecycle"))
local MonsterAgentLifecycle = require(script.Parent:WaitForChild("MonsterAgentLifecycle"))
local MonsterRigBuilder = require(script.Parent:WaitForChild("MonsterRigBuilder"))
local MonsterSpawnGeometry = require(script.Parent:WaitForChild("MonsterSpawnGeometry"))
local MonsterAnimationTrackFactory = require(script.Parent:WaitForChild("MonsterAnimationTrackFactory"))
local MonsterInitialAttributes = require(script.Parent:WaitForChild("MonsterInitialAttributes"))
local MonsterWanderController = require(script.Parent:WaitForChild("MonsterWanderController"))
local MonsterDeathLifecycle = require(script.Parent:WaitForChild("MonsterDeathLifecycle"))
local MonsterIdlePresentation = require(script.Parent:WaitForChild("MonsterIdlePresentation"))
local MonsterPopulationController = require(script.Parent:WaitForChild("MonsterPopulationController"))
local MonsterSpawnPresentation = require(script.Parent:WaitForChild("MonsterSpawnPresentation"))
local Balance = require(Shared:WaitForChild("balance"):WaitForChild("Balance"))
local TestAppearance = require(script.Parent.Parent:WaitForChild("dev"):WaitForChild("GameplayTestAppearance"))
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
    Demand.Remove(model)
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
    for _, connection in ipairs(entry.idleConnections or {}) do connection:Disconnect() end
    table.clear(entry.idleConnections or {})
    idlePresentation.stopIdleState(entry)
    idlePresentation.stopTrack(entry.combatIdleTrack)
    idlePresentation.stopTrack(entry.deathTrack)
    if externallyDestroying then
        -- Deferred Destroying signals can run after the instance is locked.
        -- Detach removes its hitbox binding first; remaining attribute writes are best effort.
        pcall(EntityHitboxService.Detach, model)
    else
        MonsterAgentLifecycle.Unbind(model)
        EntityHitboxService.Detach(model)
        if entry.rigLease then entry.rigLease:Release() end
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

local function bindIdleGeneration(state, model, entry)
    local connections = {}
    entry.idleConnections = connections
    idlePresentation.BindIdleEvents(model, entry, function(signal, callback)
        table.insert(connections, signal:Connect(callback))
    end, function()
        return state.instances[model] == entry and entry.idleConnections == connections
    end)
end

local function releaseLivePose(model, entry)
    model:SetAttribute("Damageable", false)
    model:SetAttribute("Game1MnpcRigReady", false)
    MonsterAgentLifecycle.DetachPose(model)
    for _, connection in ipairs(entry.idleConnections or {}) do connection:Disconnect() end
    entry.idleConnections = nil
    local tracks = {}
    for _, choice in ipairs(entry.idleChoices or {}) do tracks[choice.track] = true end
    for _, field in ipairs({"idleTrack", "combatIdleTrack", "walkTrack", "runTrack", "deathTrack"}) do
        local track = entry[field]
        if track then tracks[track] = true end
        entry[field] = nil
    end
    for track in pairs(tracks) do track:Destroy() end
    entry.idleChoices = {}
    entry.activeIdleSpecial = nil
    EntityHitboxService.Detach(model)
    if entry.rigLease then entry.rigLease:Release() end
    entry.rigLease = nil
    entry.visual = nil
    entry.spawnPresentation = nil -- completed reveal owns references to the old rig
    return true
end

local function spawnOne(state: any): Model?
    local record = state.record
    local slug = tostring(record.monsterSlug or "")
    local definition = monsterDefinition(slug)
    if record.balanceId and not record.testOwner then
        local row = Balance.Monster(record.balanceId)
        local matched, bound, matches, bindings = nil, nil, 0, 0
        if row and row.nameEn ~= "" then
            for key, candidate in pairs(MonsterRegistry.monsters or {}) do
                if string.lower(candidate.nameEn or "") == string.lower(row.nameEn or "") then
                    matched = candidate; matches += 1
                    local binding = Balance.MonsterForModel(key)
                    if binding and binding.id == row.id then bound = candidate; bindings += 1 end
                end
            end
        end
        definition = if bindings == 1 then bound elseif matches == 1 then matched else nil
        if not definition then
            warn("[game1][monster-spawn] pending model for Database row " .. tostring(record.balanceId))
            return nil
        end
        slug = definition.slug
        local profile = MonsterAnimationRegistry.profiles and MonsterAnimationRegistry.profiles[slug]
        for _, slot in ipairs({"walk", "run", "combat_idle", "attack", "death"}) do
            local clips = profile and profile.slots and profile.slots[slot]
            if not clips or #clips == 0 then
                warn("[game1][monster-spawn] pending animations for " .. slug .. " · " .. slot)
                return nil
            end
        end
    end
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

    local instanceId = tostring(record.spawnId or "spawn") .. "-" .. tostring(math.floor(os.clock() * 1000)) .. "-" .. tostring(spawnRandom:NextInteger(1000, 9999))
    local surface = if record.testOwner then record.testSurface else spawnGeometry:RandomSpawnPoint(record)
    local yaw = if record.testOwner then math.rad(record.testYaw) else spawnRandom:NextNumber(0, math.pi * 2)
    local model, navigationRoot, humanoid = MnpcLifecycle.Create(slug .. "_" .. instanceId:sub(-4), surface, yaw, "Monster")
    MnpcLifecycle.CopyTemplateMetadata(model, template)
    if record.testOwner then state.testConstructing = model end
    MonsterInitialAttributes.Apply(model, definition, record, instanceId)
    model:SetAttribute("Game1MnpcFullModelId", tostring(definition.modelAssetId or ""))
    model:SetAttribute("Damageable", false)
    local prepared = MnpcLifecycle.PrepareShell(model, navigationRoot, template, surface, yaw, "Monster")
    local riseFromGround = not record.testOwner and definition.behavior and definition.behavior.riseFromGround == true
    local initialShell = prepared ~= nil and not record.testOwner and not riseFromGround
        and Demand.CanSpawnShell(model, navigationRoot, template)
    local visual, rigLease
    if not initialShell then
        visual, rigLease = MnpcLifecycle.AttachRig(model, navigationRoot, template, surface, yaw, "Monster", prepared)
        if not visual then
            model:Destroy()
            warn("[game1][monster-spawn] monster contains no usable visual rig: " .. slug)
            return nil
        end
        model:SetAttribute("RuntimeAnimationRootBridgeCount", MonsterRigBuilder.EnsureRuntimeAnimationRoot(visual))
    end
    -- The GP inspection mode keeps its existing per-player persistent proxy.
    local persistentOwner = if RunService:IsStudio() and Workspace.StreamingEnabled
        and record.testOwner and record.testZone and record.testZone <= 6
        then Players:GetPlayerByUserId(record.testOwner) else nil
    if persistentOwner then model.ModelStreamingMode = Enum.ModelStreamingMode.PersistentPerPlayer end
    -- A previously qualified distant shell does not need a visual spawn reveal.
    -- Rise-from-ground and gameplay-test actors keep the original spawn path.
    model:SetAttribute("MonsterSpawning", not initialShell)
    model:SetAttribute("MonsterHomePosition", navigationRoot.Position)
    MnpcLifecycle.Publish(model, navigationRoot, ensureMonstersFolder())
    if persistentOwner then model:AddPersistentPlayer(persistentOwner) end
    if record.testOwner then
        local row = assert(Balance.Monster(record.testBalanceId))
        local color = Balance.Grade.Color(row.level)
        TestAppearance.Tint(visual, color)
        local title = if row.nameEn and row.nameEn ~= "" then row.nameEn else "Monster_" .. row.id:sub(-3)
        if row.skills then
            local names = {}
            for _, a in ipairs(row.skills) do table.insert(names, Balance.Skill(a.skillId).name) end
            title = table.concat(names, " + ")
        end
        local proxy = row.nameEn ~= "Gremlin" or row.skills ~= nil
        if record.testKind ~= "group" and (not record.testZone or record.testZone > 6) then
            TestAppearance.Label(model, ("%s · %s · LVL %d\n%d HP · %d ATK"):format(title .. (if proxy then " [proxy]" else ""), row.type, row.level, row.hp, row.damage), color)
        end
        model:SetAttribute("MonsterDisplayName", title)
        model:SetAttribute("GameplayTestVisualPlaceholder", proxy)
    end
    local spawnPresentation, hitbox
    local entry = {idleChoices = {}}
    if not initialShell then
        spawnPresentation = MonsterSpawnPresentation.Prepare(model, visual, navigationRoot, humanoid, riseFromGround)
        hitbox = EntityHitboxService.Attach(model, visual)
        model:SetAttribute("CombatHitboxCount", hitbox.count)
        entry = MonsterAnimationTrackFactory.Load(
            MonsterAnimationRegistry.profiles and MonsterAnimationRegistry.profiles[slug], model, visual
        )
    end
    entry.visual = visual
    entry.rigLease = rigLease
    entry.navigationRoot = navigationRoot
    entry.humanoid = humanoid
    entry.wandering = false
    entry.dying = false
    entry.deathPoseHeld = false
    entry.connections = {}
    entry.spawnPresentation = spawnPresentation
    population:RegisterInstance(state, model, entry)

    if spawnPresentation then
        bindIdleGeneration(state, model, entry)
        idlePresentation.playBaseIdle(model, entry)
        spawnPresentation:Start(function()
            if state.instances[model] == entry and not entry.dying then
                if not record.testOwner then wanderController:Start(state, model, entry) end
            end
        end)
    else
        wanderController:Start(state, model, entry)
    end

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
    watch(entry, model:GetAttributeChangedSignal("LifeState"), function()
        if state.instances[model] ~= entry then
            return
        end
        if tostring(model:GetAttribute("LifeState") or "") == "Dying" then
            entry.diedAt = os.clock()
            if entry.spawnPresentation then entry.spawnPresentation:Cancel() end
            Demand.Remove(model)
            if entry.visual and entry.deathTrack then
                deathLifecycle:Begin(state, model, entry)
            elseif model:GetAttribute("Game1MnpcDemandStage") ~= nil then
                -- An externally forced death of a sleeping shell cannot play a
                -- corpse animation. Retire the occupied population slot once.
                releaseInstance(state, model, true)
            else
                deathLifecycle:Begin(state, model, entry)
            end
        end
    end)
    watch(entry, model.Destroying, function()
        -- External Model:Destroy must release connections, tracks and hitbox too.
        if state.instances[model] == entry then
            releaseInstance(state, model, false, true)
        end
    end)
    if not initialShell then MnpcLifecycle.MarkRigReady(model) end
    if prepared and not record.testOwner and (initialShell or (hitbox and hitbox.count > 0 and entry.deathTrack)) then
        Demand.Register(model, {
            canRelease = function()
                return model:GetAttribute("Damageable") == true and MonsterAgentLifecycle.HasPose(model)
            end,
            release = function() return releaseLivePose(model, entry) end,
            acquire = function(alive)
                local nextVisual, nextLease = MnpcLifecycle.AttachRig(model, navigationRoot, template, surface, yaw, "Monster", prepared)
                if not nextVisual then return false end
                entry.visual, entry.rigLease = nextVisual, nextLease
                model:SetAttribute("RuntimeAnimationRootBridgeCount", MonsterRigBuilder.EnsureRuntimeAnimationRoot(nextVisual))
                local nextHitbox = EntityHitboxService.Attach(model, nextVisual)
                if not alive() then pcall(EntityHitboxService.Detach, model); return false end
                if nextHitbox.count <= 0 then return false end
                local nextTracks = MonsterAnimationTrackFactory.Load(
                    MonsterAnimationRegistry.profiles and MonsterAnimationRegistry.profiles[slug], model, nextVisual)
                if not alive() then
                    -- The rig owner may already have destroyed its Animator.
                    return false
                end
                for field, value in pairs(nextTracks) do entry[field] = value end
                if not entry.deathTrack then return false end
                bindIdleGeneration(state, model, entry)
                if entry.wandering then
                    wanderController:Refresh(model, entry)
                elseif model:GetAttribute("InCombat") == true then
                    idlePresentation.playCombatIdleState(model, entry)
                else
                    idlePresentation.playBaseIdle(model, entry)
                end
                MnpcLifecycle.MarkRigReady(model)
                return true
            end,
            ready = function() return MonsterAgentLifecycle.HasPose(model) end,
        }, initialShell, template)
    end
    return model
end

-- Population owns spawn records, live slots, maxAlive and delayed respawns.
-- The callback is injected to keep instance construction and presentation in Spawner.
population = MonsterPopulationController.new(spawnOne)

function MonsterSpawnerService.TestTemplateSize(): Vector3?
    local definition = monsterDefinition("gremlin")
    local template = definition and resolvePath(tostring(definition.serverStoragePath or ""))
    return if template and template:IsA("Model") then template:GetExtentsSize() else nil
end
function MonsterSpawnerService.AddTest(record: any): any
    assert(started and record.testOwner and Balance.Monster(record.testBalanceId), "Invalid test spawn")
    return population:AddTest(record, function(state, model)
        if state.instances[model] then releaseInstance(state, model, false)
        elseif model.Parent then model:Destroy() end
    end)
end
function MonsterSpawnerService.FillTest(state: any): Model?
    return population:FillTest(state)
end
function MonsterSpawnerService.RemoveTest(state: any)
    population:RemoveTest(state)
end

function MonsterSpawnerService.Start()
    if started then
        return
    end
    started = true
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
