local ReplicatedStorage = game:GetService("ReplicatedStorage")
local ServerStorage = game:GetService("ServerStorage")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local MonsterShared = Shared:WaitForChild("monster")
local CharacterShared = Shared:WaitForChild("character")
local CharacterMovementConfig = require(CharacterShared:WaitForChild("CharacterMovementConfig"))
local MonsterRegistry = require(MonsterShared:WaitForChild("MonsterRegistry"))
local MonsterAnimationRegistry = require(MonsterShared:WaitForChild("MonsterAnimationRegistry"))
local EntityHitboxService = require(script.Parent.Parent:WaitForChild("combat"):WaitForChild("EntityHitboxService"))
local SpawnRegistry = require(script.Parent:WaitForChild("MonsterSpawnRegistry"))

local MonsterSpawnerService = {}
local started = false
local spawnRandom = Random.new()
local states = {}
local monstersFolder: Folder? = nil

local DEATH_FALLBACK_SECONDS = 2.5
local GROUND_RAY_START = 96
local GROUND_RAY_LENGTH = 384
local NAVIGATION_ROOT_SIZE = Vector3.new(2, 2, 1)
local NAVIGATION_HIP_HEIGHT = 1.8
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

local function animationProfile(slug: string): any?
    local profiles = MonsterAnimationRegistry.profiles
    return profiles and profiles[slug] or nil
end

local function publishedRows(profile: any?, slot: string): {any}
    local slots = profile and profile.slots
    local rows = slots and slots[slot]
    if typeof(rows) ~= "table" then
        return {}
    end
    local result = {}
    for _, row in ipairs(rows) do
        if tostring(row.animationId or ""):match("^rbxassetid://%d+$") then
            table.insert(result, row)
        end
    end
    return result
end

local function firstPublishedTrack(profile: any?, slot: string): any?
    return publishedRows(profile, slot)[1]
end

local function animatorFor(runtimeModel: Model, visual: Model): Animator
    -- Keep the animation host inside the visual rig, separate from the navigation
    -- Humanoid on the runtime wrapper. This mirrors the RobloxLineage contract:
    -- Humanoid owns locomotion of the wrapper; AnimationController owns the bones.
    local controller = visual:FindFirstChildOfClass("AnimationController")
        or visual:FindFirstChildWhichIsA("AnimationController", true)
        or runtimeModel:FindFirstChildOfClass("AnimationController")
        or runtimeModel:FindFirstChildWhichIsA("AnimationController", true)
    if not controller then
        controller = Instance.new("AnimationController")
        controller.Name = "AnimationController"
        controller.Parent = visual
    elseif controller.Parent ~= visual then
        controller.Parent = visual
    end

    for _, descendant in ipairs(runtimeModel:GetDescendants()) do
        if descendant:IsA("AnimationController") and descendant ~= controller then
            descendant:Destroy()
        end
    end

    local animator = controller:FindFirstChildOfClass("Animator")
    if not animator then
        animator = Instance.new("Animator")
        animator.Name = "Animator"
        animator.Parent = controller
    end
    return animator
end

local function animationPriority(value: any): Enum.AnimationPriority
    local name = tostring(value or "")
    if name == "Idle" then
        return Enum.AnimationPriority.Idle
    elseif name == "Movement" then
        return Enum.AnimationPriority.Movement
    elseif name == "Action2" then
        return Enum.AnimationPriority.Action2
    elseif name == "Action3" then
        return Enum.AnimationPriority.Action3
    elseif name == "Action4" then
        return Enum.AnimationPriority.Action4
    end
    return Enum.AnimationPriority.Action
end

local function loadAnimationTrack(animator: Animator?, row: any?, looped: boolean): AnimationTrack?
    if not animator or not row then
        return nil
    end
    local animationId = tostring(row.animationId or "")
    if not animationId:match("^rbxassetid://%d+$") then
        return nil
    end
    local animation = Instance.new("Animation")
    animation.AnimationId = animationId
    local ok, result = pcall(function()
        return animator:LoadAnimation(animation)
    end)
    animation:Destroy()
    if not ok then
        warn("[game1][monster-spawn] animation load failed: " .. tostring(result))
        return nil
    end
    local track = result :: AnimationTrack
    track.Looped = looped
    track.Priority = animationPriority(row.priority)
    return track
end

local function stopTrack(track: AnimationTrack?)
    if not track then
        return
    end
    pcall(function()
        track:Stop(0.08)
    end)
end

local function idleRole(row: any): string
    local role = tostring(row.role or "")
    if role ~= "" then
        return role
    end
    if tostring(row.sourceSlot or "") == "idle_special" or finite(row.variant, 0) > 0 then
        return "special"
    end
    return "base"
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
    if entry.dying then
        return
    end
    stopTrack(entry.walkTrack)
    model:SetAttribute("MonsterAnimationState", "idle")
    model:SetAttribute("MonsterIdleVariant", "base")
    if entry.idleTrack and not entry.idleTrack.IsPlaying then
        pcall(function()
            entry.idleTrack:Play(0.12)
        end)
    end
end

local function maybePlayIdleSpecial(model: Model, entry: any)
    if entry.dying or entry.activeIdleSpecial ~= nil then
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
        choice.track:Play(0.08)
    end)
    if not ok then
        entry.activeIdleSpecial = nil
        playBaseIdle(model, entry)
    end
end

local function visibleBounds(model: Model): (CFrame, Vector3)
    local minimum = Vector3.new(math.huge, math.huge, math.huge)
    local maximum = Vector3.new(-math.huge, -math.huge, -math.huge)
    local found = false
    for _, descendant in ipairs(model:GetDescendants()) do
        if descendant:IsA("BasePart") and descendant.Name ~= "RootPart" and descendant.Name ~= "RootCollider" then
            found = true
            local half = descendant.Size * 0.5
            for x = -1, 1, 2 do
                for y = -1, 1, 2 do
                    for z = -1, 1, 2 do
                        local corner = descendant.CFrame:PointToWorldSpace(Vector3.new(half.X * x, half.Y * y, half.Z * z))
                        minimum = Vector3.new(math.min(minimum.X, corner.X), math.min(minimum.Y, corner.Y), math.min(minimum.Z, corner.Z))
                        maximum = Vector3.new(math.max(maximum.X, corner.X), math.max(maximum.Y, corner.Y), math.max(maximum.Z, corner.Z))
                    end
                end
            end
        end
    end
    if not found then
        return model:GetBoundingBox()
    end
    local size = maximum - minimum
    return CFrame.new((minimum + maximum) * 0.5), size
end

local function prepareVisual(runtimeModel: Model): (Model, BasePart?)
    local visual = runtimeModel:FindFirstChild("ImportedRig")
    if not visual or not visual:IsA("Model") then
        visual = runtimeModel
    end
    for _, descendant in ipairs(runtimeModel:GetDescendants()) do
        if descendant:IsA("BasePart") then
            descendant.Anchored = false
            descendant.CanCollide = false
            descendant.CanTouch = false
            descendant.CanQuery = false
            descendant.Massless = true
        elseif descendant:IsA("Humanoid") then
            descendant:Destroy()
        end
    end
    local visualRoot = visual:FindFirstChild("RootPart", true)
        or visual.PrimaryPart
        or visual:FindFirstChildWhichIsA("MeshPart", true)
        or visual:FindFirstChildWhichIsA("BasePart", true)
    return visual :: Model, if visualRoot and visualRoot:IsA("BasePart") then visualRoot else nil
end

local function createNavigationRig(runtimeModel: Model, visual: Model, visualRoot: BasePart, surface: Vector3, yawRadians: number): (BasePart?, Humanoid?)
    -- Never weld every visual BasePart to the navigation root. Doing so turns an
    -- articulated Motor6D rig into one rigid physics assembly and can also fight
    -- imported rig constraints. Move the monster through one visual root only;
    -- all Bone/Motor6D articulation below that root remains animation-owned.
    local navigationRoot = Instance.new("Part")
    navigationRoot.Name = "HumanoidRootPart"
    navigationRoot.Size = NAVIGATION_ROOT_SIZE
    navigationRoot.CFrame = CFrame.new(
        surface + Vector3.new(0, NAVIGATION_ROOT_SIZE.Y * 0.5 + NAVIGATION_HIP_HEIGHT, 0)
    ) * CFrame.Angles(0, yawRadians, 0)
    navigationRoot.Transparency = 1
    navigationRoot.CastShadow = false
    navigationRoot.Anchored = false
    navigationRoot.CanCollide = true
    navigationRoot.CanTouch = false
    navigationRoot.CanQuery = false
    navigationRoot.Massless = false
    navigationRoot.Parent = runtimeModel

    local boxCFrame, boxSize = visibleBounds(visual)
    local root = Instance.new("Part")
    root.Name = "RootCollider"
    -- Broadphase only. Precise combat uses EntityHitboxService's virtual bone regions.
    root.Size = Vector3.new(math.max(0.5, boxSize.X), math.max(0.5, boxSize.Y), math.max(0.5, boxSize.Z))
    root.CFrame = boxCFrame
    root.Transparency = 1
    root.CastShadow = false
    root.Anchored = false
    root.CanCollide = false
    root.CanTouch = false
    root.CanQuery = true
    root.Massless = true
    root.Parent = runtimeModel

    local rootWeld = Instance.new("WeldConstraint")
    rootWeld.Name = "RootColliderWeld"
    rootWeld.Part0 = navigationRoot
    rootWeld.Part1 = root
    rootWeld.Parent = navigationRoot

    local visualWeld = Instance.new("WeldConstraint")
    visualWeld.Name = "VisualRootWeld"
    visualWeld.Part0 = root
    visualWeld.Part1 = visualRoot
    visualWeld.Parent = root

    local humanoid = Instance.new("Humanoid")
    humanoid.Name = "Humanoid"
    humanoid.RequiresNeck = false
    humanoid.BreakJointsOnDeath = false
    humanoid.AutoRotate = true
    humanoid.HipHeight = NAVIGATION_HIP_HEIGHT
    humanoid.UseJumpPower = false
    humanoid.JumpHeight = 0
    humanoid.MaxSlopeAngle = 89
    humanoid:SetStateEnabled(Enum.HumanoidStateType.Jumping, false)
    humanoid.WalkSpeed = 0
    humanoid.MaxHealth = 1
    humanoid.Health = 1
    humanoid.HealthDisplayType = Enum.HumanoidHealthDisplayType.AlwaysOff
    humanoid.DisplayDistanceType = Enum.HumanoidDisplayDistanceType.None
    humanoid.NameDisplayDistance = 0
    humanoid.Parent = runtimeModel

    runtimeModel.PrimaryPart = navigationRoot
    pcall(function() navigationRoot:SetNetworkOwner(nil) end)
    return navigationRoot, humanoid
end

local function spawnCenter(record: any): Vector3
    local position = record.position or {}
    return Vector3.new(finite(position.x, 0), finite(position.y, 0), finite(position.z, 0))
end

local function surfacePoint(candidate: Vector3): Vector3
    local params = RaycastParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    params.FilterDescendantsInstances = { ensureMonstersFolder() }
    params.IgnoreWater = false
    params.RespectCanCollide = false
    local origin = candidate + Vector3.new(0, GROUND_RAY_START, 0)
    local hit = Workspace:Raycast(origin, Vector3.new(0, -GROUND_RAY_LENGTH, 0), params)
    return if hit then hit.Position else candidate
end

local function randomSpawnPoint(record: any): Vector3
    local center = spawnCenter(record)
    local radius = math.max(0, finite(record.spawnRadius, 0))
    local candidate = center
    if radius > 0 then
        local angle = spawnRandom:NextNumber(0, math.pi * 2)
        local distance = math.sqrt(spawnRandom:NextNumber(0, 1)) * radius
        candidate = center + Vector3.new(math.cos(angle) * distance, 0, math.sin(angle) * distance)
    end
    return surfacePoint(candidate)
end

local function groundAlign(model: Model, surface: Vector3, yawRadians: number)
    local sourcePivot = model:GetPivot()
    local sourceRotation = sourcePivot.Rotation
    model:PivotTo(CFrame.new(surface) * CFrame.Angles(0, yawRadians, 0) * sourceRotation)
    local boxCFrame, boxSize = visibleBounds(model)
    local bottomY = boxCFrame.Position.Y - boxSize.Y * 0.5
    model:PivotTo(model:GetPivot() + Vector3.new(0, surface.Y - bottomY, 0))
end

local function horizontalDistance(left: Vector3, right: Vector3): number
    return Vector3.new(right.X - left.X, 0, right.Z - left.Z).Magnitude
end

local function walkSpeedFor(model: Model): number
    return CharacterMovementConfig.ResolveSpeed(nil, model:GetAttribute("RunSpeed"), "Walk")
end

local function chooseWanderTarget(record: any, current: Vector3): (Vector3?, number, boolean)
    local center = spawnCenter(record)
    local radius = math.max(0, finite(record.spawnRadius, 0))
    if radius <= 0 then
        return nil, 0, false
    end

    local toCenter = Vector3.new(center.X - current.X, 0, center.Z - current.Z)
    local distanceToCenter = toCenter.Magnitude
    local outsideSpawn = distanceToCenter > radius
    local maximumLength = radius * 2
    local direction: Vector3
    if outsideSpawn and distanceToCenter > 0.001 then
        -- Same contract as RobloxLineage: if a straight wander route ended outside
        -- the authored circle, the next route is forced inward and cannot pass the center.
        direction = toCenter.Unit
        maximumLength = math.min(maximumLength, distanceToCenter)
    else
        local angle = spawnRandom:NextNumber(0, math.pi * 2)
        direction = Vector3.new(math.cos(angle), 0, math.sin(angle))
    end
    if maximumLength <= 0.001 then
        return nil, 0, outsideSpawn
    end

    local routeLength = spawnRandom:NextNumber(0, maximumLength)
    local flatDestination = current + direction * routeLength
    local destination = surfacePoint(Vector3.new(flatDestination.X, current.Y, flatDestination.Z))
    return destination, routeLength, outsideSpawn
end

local function stopWanderMovement(entry: any)
    entry.wandering = false
    stopTrack(entry.walkTrack)
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

            local navigationRoot = entry.navigationRoot
            local humanoid = entry.humanoid
            if not navigationRoot or not navigationRoot.Parent or not humanoid or not humanoid.Parent then
                break
            end
            local destination, routeLength, outsideSpawn = chooseWanderTarget(state.record, navigationRoot.Position)
            if not destination or routeLength <= WANDER_ARRIVAL_TOLERANCE then
                continue
            end

            stopIdleState(entry)
            entry.wandering = true
            model:SetAttribute("MonsterAnimationState", "walk")
            model:SetAttribute("MonsterIdleVariant", nil)
            model:SetAttribute("MonsterWanderTargetX", destination.X)
            model:SetAttribute("MonsterWanderTargetZ", destination.Z)
            model:SetAttribute("MonsterWanderRouteLength", routeLength)
            model:SetAttribute("MonsterWanderOutsideSpawn", outsideSpawn)
            if entry.walkTrack then
                pcall(function() entry.walkTrack:Play(0.1) end)
            end

            local speed = math.max(0.1, walkSpeedFor(model))
            humanoid.WalkSpeed = speed
            humanoid.AutoRotate = true
            humanoid:MoveTo(destination)
            local finished = false
            local moveConnection = humanoid.MoveToFinished:Connect(function()
                finished = true
            end)
            local deadline = os.clock() + math.max(8, routeLength / speed + 4)
            local nextRefresh = os.clock() + WANDER_MOVE_REFRESH_SECONDS
            while not finished
                and state.instances[model] == entry
                and model.Parent
                and not entry.dying
                and os.clock() < deadline
            do
                task.wait(0.1)
                if horizontalDistance(navigationRoot.Position, destination) <= WANDER_ARRIVAL_TOLERANCE then
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
                playBaseIdle(model, entry)
            end
        end
    end)
end

local function applyMonsterAttributes(model: Model, definition: any, record: any, instanceId: string)
    local stats = definition.stats or {}
    local maxHP = math.max(1, finite(stats.MaxHP, 100))
    model:SetAttribute("Game1MonsterRuntime", true)
    model:SetAttribute("MonsterSlug", tostring(definition.slug or record.monsterSlug or ""))
    model:SetAttribute("SpawnId", tostring(record.spawnId or ""))
    model:SetAttribute("MonsterInstanceId", instanceId)
    model:SetAttribute("Damageable", true)
    model:SetAttribute("LifeState", "Alive")
    model:SetAttribute("MaxHP", maxHP)
    model:SetAttribute("HP", maxHP)
    model:SetAttribute("Damage", math.max(0, finite(stats.Damage, 10)))
    model:SetAttribute("AttackSpeed", math.max(1, finite(stats.AttackSpeed, 100)))
    model:SetAttribute("RunSpeed", math.max(0, finite(stats.RunSpeed, 16)))
    model:SetAttribute("CritChance", math.clamp(finite(stats.CritChance, 0), 0, 100))
    model:SetAttribute("Defense", math.max(0, finite(stats.Defense, 0)))
end

local function releaseInstance(state: any, model: Model, scheduleRespawn: boolean)
    local entry = state.instances[model]
    if entry == nil then
        return
    end
    state.instances[model] = nil
    stopWanderMovement(entry)
    stopIdleState(entry)
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

local function beginDeath(state: any, model: Model, entry: any)
    if entry.dying then
        return
    end
    entry.dying = true
    model:SetAttribute("Damageable", false)
    model:SetAttribute("MonsterAnimationState", "death")
    model:SetAttribute("MonsterIdleVariant", nil)
    stopWanderMovement(entry)
    stopIdleState(entry)
    if entry.navigationRoot and entry.navigationRoot.Parent then
        entry.navigationRoot.AssemblyLinearVelocity = Vector3.zero
        entry.navigationRoot.AssemblyAngularVelocity = Vector3.zero
        entry.navigationRoot.Anchored = true
    end
    local track = entry.deathTrack
    local holdSeconds = DEATH_FALLBACK_SECONDS
    if track then
        pcall(function()
            track:Play(0.08)
        end)
        local deadline = os.clock() + 0.75
        while track.Length <= 0.01 and os.clock() < deadline and model.Parent do
            task.wait(0.05)
        end
        if track.Length > 0.01 then
            holdSeconds = math.max(0.25, track.Length)
        end
    end
    task.delay(holdSeconds, function()
        releaseInstance(state, model, true)
    end)
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
    local visual, visualRoot = prepareVisual(model)
    if not visualRoot then
        model:Destroy()
        warn("[game1][monster-spawn] monster contains no usable BasePart: " .. slug)
        return nil
    end
    local surface = randomSpawnPoint(record)
    local yaw = spawnRandom:NextNumber(0, math.pi * 2)
    groundAlign(model, surface, yaw)
    applyMonsterAttributes(model, definition, record, instanceId)
    local navigationRoot, humanoid = createNavigationRig(model, visual, visualRoot, surface, yaw)
    if not navigationRoot or not humanoid then
        model:Destroy()
        warn("[game1][monster-spawn] monster navigation rig could not be created: " .. slug)
        return nil
    end
    local hitbox = EntityHitboxService.Attach(model, visual)
    model:SetAttribute("PoseHitboxCount", hitbox.count)

    local profile = animationProfile(slug)
    local animator = animatorFor(model, visual)
    local idleTrack: AnimationTrack? = nil
    local idleChoices = {}
    for _, row in ipairs(publishedRows(profile, "idle")) do
        local role = idleRole(row)
        local track = loadAnimationTrack(animator, row, role == "base")
        if track then
            local choice = { row = row, track = track, role = role }
            table.insert(idleChoices, choice)
            if role == "base" and not idleTrack then
                idleTrack = track
            end
        end
    end
    local walkTrack = loadAnimationTrack(animator, firstPublishedTrack(profile, "walk") or firstPublishedTrack(profile, "run"), true)
    local deathTrack = loadAnimationTrack(animator, firstPublishedTrack(profile, "death"), false)
    local entry = {
        idleTrack = idleTrack,
        idleChoices = idleChoices,
        activeIdleSpecial = nil,
        walkTrack = walkTrack,
        deathTrack = deathTrack,
        navigationRoot = navigationRoot,
        humanoid = humanoid,
        wandering = false,
        dying = false,
    }
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

    model:GetAttributeChangedSignal("LifeState"):Connect(function()
        if state.instances[model] ~= entry then
            return
        end
        if tostring(model:GetAttribute("LifeState") or "") == "Dead" then
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
        if model.Parent and tostring(model:GetAttribute("LifeState") or "") ~= "Dead" then
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
