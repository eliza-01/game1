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
local AnimationFirstFrameSeam = require(AnimationShared:WaitForChild("AnimationFirstFrameSeam"))
local MonsterRegistry = require(MonsterShared:WaitForChild("MonsterRegistry"))
local MonsterAnimationRegistry = require(MonsterShared:WaitForChild("MonsterAnimationRegistry"))
local CombatRoot = script.Parent.Parent:WaitForChild("combat")
local EntityHitboxService = require(CombatRoot:WaitForChild("EntityHitboxService"))
local DeathLifecycleService = require(CombatRoot:WaitForChild("DeathLifecycleService"))
local DeathAnimationPolicy = require(Shared:WaitForChild("combat"):WaitForChild("DeathAnimationPolicy"))
local SpawnRegistry = require(script.Parent:WaitForChild("MonsterSpawnRegistry"))

local MonsterSpawnerService = {}
local started = false
local spawnRandom = Random.new()
local states = {}
local monstersFolder: Folder? = nil

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

local function animationPlaybackPercent(model: Model, channel: string): number
    return AnimationSpeedScaling.ResolveForModel(model, channel)
end

local function animationPlaybackScale(model: Model, channel: string): number
    return animationPlaybackPercent(model, channel) / 100
end

local function createRuntimeSeam(animator: Animator?, row: any?, primary: AnimationTrack?, looped: boolean)
    if not animator or not row or not primary or row.duplicateFirstFrameAtEnd ~= true then
        return nil
    end
    local companion = loadAnimationTrack(animator, row, false)
    if not companion then
        return nil
    end
    return AnimationFirstFrameSeam.new(primary, companion, looped)
end

local function playTrackAtConfiguredSpeed(model: Model, track: AnimationTrack?, channel: string, fadeTime: number, seam: any?)
    if not track then
        return
    end
    local percent = animationPlaybackPercent(model, channel)
    model:SetAttribute("AnimationPlaybackSpeedPercent", percent)
    local speed = percent / 100
    if seam then
        if seam:IsPlaying() then
            seam:AdjustSpeed(speed)
        else
            seam:Play(fadeTime, speed)
        end
    elseif track.IsPlaying then
        track:AdjustSpeed(speed)
    else
        track:Play(fadeTime, 1, speed)
    end
end

local function stopTrack(track: AnimationTrack?, seam: any?)
    if seam then
        seam:Stop(0.08)
        return
    end
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
    stopTrack(entry.idleTrack, entry.idleSeam)
    for _, choice in ipairs(entry.idleChoices or {}) do
        if choice.role == "special" then
            stopTrack(choice.track, choice.seam)
        end
    end
    entry.activeIdleSpecial = nil
end

local function playBaseIdle(model: Model, entry: any)
    if entry.dying or model:GetAttribute("MonsterCombatActive") == true or model:GetAttribute("InCombat") == true then
        return
    end
    stopTrack(entry.walkTrack, entry.walkSeam)
    stopTrack(entry.runTrack, entry.runSeam)
    model:SetAttribute("MonsterAnimationState", "idle")
    model:SetAttribute("MonsterIdleVariant", "base")
    if entry.idleTrack then
        pcall(function()
            playTrackAtConfiguredSpeed(model, entry.idleTrack, "idle", 0.12, entry.idleSeam)
        end)
    end
end

local function playCombatIdleState(model: Model, entry: any)
    if entry.dying or model:GetAttribute("MonsterCombatActive") == true then
        return
    end
    stopIdleState(entry)
    stopTrack(entry.walkTrack, entry.walkSeam)
    stopTrack(entry.runTrack, entry.runSeam)
    model:SetAttribute("MonsterAnimationState", "combat_idle")
    model:SetAttribute("MonsterIdleVariant", "combat")
    if entry.combatIdleTrack then
        pcall(function()
            playTrackAtConfiguredSpeed(model, entry.combatIdleTrack, "combat_idle", 0.1, entry.combatIdleSeam)
        end)
    end
end

local function maybePlayIdleSpecial(model: Model, entry: any)
    if entry.dying or entry.activeIdleSpecial ~= nil or model:GetAttribute("InCombat") == true then
        return
    end
    local choice = weightedIdleChoice(entry.idleChoices or {})
    if not choice or choice.role ~= "special" then
        return
    end
    entry.activeIdleSpecial = choice
    stopTrack(entry.idleTrack, entry.idleSeam)
    model:SetAttribute("MonsterAnimationState", "idle")
    model:SetAttribute("MonsterIdleVariant", ("special_%02d"):format(math.max(1, math.floor(finite(choice.row.variant, 1)))))
    local ok = pcall(function()
        playTrackAtConfiguredSpeed(model, choice.track, "idle", 0.08, choice.seam)
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

local function ensureRuntimeAnimationRoot(visual: Model): number
    -- Studio's Animation Editor exports skinned FBX clips with a synthetic
    -- RootBone pose above the authored skeleton root. Runtime Animator ignores
    -- animation on a Bone that is itself the root of a MeshPart hierarchy.
    -- Materialize that neutral RootBone in the runtime clone so the authored
    -- root bone (for example `spine`) becomes an ordinary animated child.
    --
    -- The helper is identity-only and is added before tracks are loaded. Existing
    -- authored Bone world/rest transforms are therefore unchanged. The navigation
    -- wrapper remains responsible only for world locomotion/yaw; animation owns
    -- the complete authored bone pose, including root-bone translation/rotation.
    local bridged = 0
    for _, descendant in ipairs(visual:GetDescendants()) do
        if descendant:IsA("MeshPart") then
            local directBones = {}
            local animationRoot: Bone? = nil
            for _, child in ipairs(descendant:GetChildren()) do
                if child:IsA("Bone") then
                    if child.Name == "RootBone" then
                        animationRoot = child
                    else
                        table.insert(directBones, child)
                    end
                end
            end

            if #directBones > 0 then
                if not animationRoot then
                    animationRoot = Instance.new("Bone")
                    animationRoot.Name = "RootBone"
                    animationRoot.CFrame = CFrame.identity
                    animationRoot.Parent = descendant
                    animationRoot:SetAttribute("Game1RuntimeAnimationRoot", true)
                    bridged += 1
                end

                for _, bone in ipairs(directBones) do
                    -- Preserve the authored rest/world transform even if a source
                    -- asset already supplied a non-identity RootBone.
                    local authoredMeshLocal = bone.CFrame
                    bone.Parent = animationRoot
                    bone.CFrame = animationRoot.CFrame:Inverse() * authoredMeshLocal
                end
            end
        end
    end

    visual:SetAttribute("Game1RuntimeAnimationRootBridgeCount", bridged)
    return bridged
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
    -- Movement collider only. Combat uses precomputed bone-local mesh bounds.
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
    local activeSeam = if mode == "Run" then (entry.runSeam or entry.walkSeam) else (entry.walkSeam or entry.runSeam)
    local inactiveTrack = mode == "Run" and entry.walkTrack or entry.runTrack
    local inactiveSeam = mode == "Run" and entry.walkSeam or entry.runSeam
    if inactiveTrack and inactiveTrack ~= activeTrack then
        stopTrack(inactiveTrack, inactiveSeam)
    end
    if activeTrack then
        pcall(function() playTrackAtConfiguredSpeed(model, activeTrack, string.lower(mode), 0.1, activeSeam) end)
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
            local remaining = horizontalDistance(navigationRoot.Position, destination)
            entry.wanderDeadline = os.clock() + math.max(8, remaining / speed + 4)
        end
        humanoid:MoveTo(destination)
    end
end

local function stopWanderMovement(entry: any)
    entry.wandering = false
    entry.wanderDestination = nil
    entry.wanderDeadline = nil
    stopTrack(entry.walkTrack, entry.walkSeam)
    stopTrack(entry.runTrack, entry.runSeam)
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
            local destination, routeLength, outsideSpawn = chooseWanderTarget(state.record, navigationRoot.Position)
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

local function applyMonsterAttributes(model: Model, definition: any, record: any, instanceId: string)
    local stats = definition.stats or {}
    local behavior = definition.behavior or {}
    local maxHP = math.max(1, finite(stats.MaxHP, 100))
    model:SetAttribute("Game1MonsterRuntime", true)
    model:SetAttribute("MonsterSlug", tostring(definition.slug or record.monsterSlug or ""))
    model:SetAttribute("SpawnId", tostring(record.spawnId or ""))
    model:SetAttribute("MonsterInstanceId", instanceId)
    model:SetAttribute("Damageable", true)
    model:SetAttribute("LifeState", "Alive")
    model:SetAttribute("InCombat", false)
    model:SetAttribute("CombatState", "Peace")
    model:SetAttribute("CombatUntilServerTime", 0)
    model:SetAttribute("MaxHP", maxHP)
    model:SetAttribute("HP", maxHP)
    model:SetAttribute("Damage", math.max(0, finite(stats.Damage, 10)))
    model:SetAttribute("AttackSpeed", math.max(1, finite(stats.AttackSpeed, 100)))
    model:SetAttribute("RunSpeed", math.max(0, finite(stats.RunSpeed, CharacterMovementConfig.DefaultRunSpeed)))
    local debugLocomotion = tostring(Workspace:GetAttribute("Game1MonsterDebugLocomotionMode") or "Walk")
    model:SetAttribute("MonsterLocomotionMode", string.lower(debugLocomotion) == "run" and "Run" or "Walk")
    model:SetAttribute("CritChance", math.clamp(finite(stats.CritChance, 0), 0, 100))
    model:SetAttribute("Defense", math.max(0, finite(stats.Defense, 0)))
    local aggressive = behavior.aggressive == true
    local aggroRadius = math.max(0, finite(behavior.aggroRadiusStuds, 16))
    local attackRadius = math.max(0, finite(behavior.attackRadiusStuds, 3))
    model:SetAttribute("MonsterAuthoredAggressive", aggressive)
    model:SetAttribute("MonsterAuthoredAggroRadius", aggroRadius)
    model:SetAttribute("MonsterAuthoredAttackRadius", attackRadius)
    model:SetAttribute("MonsterAggressive", aggressive)
    model:SetAttribute("MonsterAggroRadius", aggroRadius)
    model:SetAttribute("MonsterAttackRadius", attackRadius)
    model:SetAttribute("MonsterCombatActive", false)
    model:SetAttribute("MonsterAttackPursuitActive", false)
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
    stopTrack(entry.combatIdleTrack, entry.combatIdleSeam)
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

local function maintainRuntimeAnimationSeams(model: Model, entry: any, deltaTimeSim: number)
    if entry.dying or model:GetAttribute("MonsterCombatActive") == true then
        return
    end

    if entry.activeIdleSpecial then
        local choice = entry.activeIdleSpecial
        if choice.seam then
            local completed = choice.seam:Step(deltaTimeSim)
            if completed and entry.activeIdleSpecial == choice then
                choice.seam:Stop(0.04)
                entry.activeIdleSpecial = nil
                playBaseIdle(model, entry)
            end
        end
        return
    end

    if entry.wandering then
        local mode = monsterLocomotionMode(model)
        local seam = if mode == "Run" then (entry.runSeam or entry.walkSeam) else (entry.walkSeam or entry.runSeam)
        if seam then
            seam:Step(deltaTimeSim)
        end
        return
    end

    if model:GetAttribute("InCombat") == true and entry.combatIdleSeam then
        entry.combatIdleSeam:Step(deltaTimeSim)
        return
    end

    if entry.idleSeam then
        local _, didLoop = entry.idleSeam:Step(deltaTimeSim)
        if didLoop then
            maybePlayIdleSpecial(model, entry)
        end
    end
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
    stopTrack(entry.combatIdleTrack, entry.combatIdleSeam)
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
    model:SetAttribute("AnimationPlaybackSpeedPercent", animationPlaybackPercent(model, "death"))
    DeathAnimationPolicy.Start(track, animationPlaybackScale(model, "death"))
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
    local animationRootBridgeCount = ensureRuntimeAnimationRoot(visual)
    model:SetAttribute("RuntimeAnimationRootBridgeCount", animationRootBridgeCount)
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
    model:SetAttribute("CombatHitboxCount", hitbox.count)

    local profile = animationProfile(slug)
    local animator = animatorFor(model, visual)
    local idleTrack: AnimationTrack? = nil
    local idleSeam = nil
    local idleChoices = {}
    for _, row in ipairs(publishedRows(profile, "idle")) do
        local role = idleRole(row)
        local track = loadAnimationTrack(animator, row, role == "base")
        if track then
            local seam = createRuntimeSeam(animator, row, track, role == "base")
            local choice = { row = row, track = track, role = role, seam = seam }
            table.insert(idleChoices, choice)
            if role == "base" and not idleTrack then
                idleTrack = track
                idleSeam = seam
            end
        end
    end
    local combatIdleRow = firstPublishedTrack(profile, "combat_idle") or firstPublishedTrack(profile, "idle")
    local walkRow = firstPublishedTrack(profile, "walk") or firstPublishedTrack(profile, "run")
    local runRow = firstPublishedTrack(profile, "run") or firstPublishedTrack(profile, "walk")
    local deathRow = firstPublishedTrack(profile, "death")
    local combatIdleTrack = loadAnimationTrack(animator, combatIdleRow, true)
    local walkTrack = loadAnimationTrack(animator, walkRow, true)
    local runTrack = loadAnimationTrack(animator, runRow, true)
    local deathTrack = loadAnimationTrack(animator, deathRow, false)
    local combatIdleSeam = createRuntimeSeam(animator, combatIdleRow, combatIdleTrack, true)
    local walkSeam = createRuntimeSeam(animator, walkRow, walkTrack, true)
    local runSeam = createRuntimeSeam(animator, runRow, runTrack, true)
    local entry = {
        idleTrack = idleTrack,
        idleSeam = idleSeam,
        idleRow = nil,
        idleChoices = idleChoices,
        activeIdleSpecial = nil,
        combatIdleTrack = combatIdleTrack,
        combatIdleSeam = combatIdleSeam,
        combatIdleRow = combatIdleRow,
        walkTrack = walkTrack,
        walkSeam = walkSeam,
        walkRow = walkRow,
        runTrack = runTrack,
        runSeam = runSeam,
        runRow = runRow,
        deathTrack = deathTrack,
        deathRow = deathRow,
        visual = visual,
        navigationRoot = navigationRoot,
        humanoid = humanoid,
        wandering = false,
        dying = false,
        deathPoseHeld = false,
    }
    for _, choice in ipairs(idleChoices) do
        if choice.role == "base" and choice.track == idleTrack then
            entry.idleRow = choice.row
            break
        end
    end
    state.instances[model] = entry

    for _, choice in ipairs(idleChoices) do
        if choice.role == "special" and not choice.seam then
            choice.track.Ended:Connect(function()
                if state.instances[model] ~= entry or entry.dying or entry.activeIdleSpecial ~= choice then
                    return
                end
                entry.activeIdleSpecial = nil
                playBaseIdle(model, entry)
            end)
        end
    end
    if idleTrack and not idleSeam then
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
            stopTrack(entry.combatIdleTrack, entry.combatIdleSeam)
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
            stopTrack(entry.combatIdleTrack, entry.combatIdleSeam)
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
                maintainRuntimeAnimationSeams(model, entry, deltaTimeSim)
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
