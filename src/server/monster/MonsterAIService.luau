-- Server-authoritative monster combat AI adapted from RobloxLineage.
-- Contract: Aggro -> Chase -> Attack. While an authored attack is still active,
-- a target that leaves weapon range is pursued directly without cancelling the
-- attack; the live target position is validated again on the Hit timeline event.
local PathfindingService = game:GetService("PathfindingService")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local MonsterShared = Shared:WaitForChild("monster")
local CombatShared = Shared:WaitForChild("combat")
local CharacterShared = Shared:WaitForChild("character")
local AnimationShared = Shared:WaitForChild("animation")
local MonsterAnimationRegistry = require(MonsterShared:WaitForChild("MonsterAnimationRegistry"))
local AttackTimelineConfig = require(CombatShared:WaitForChild("AttackTimelineConfig"))
local CharacterMovementConfig = require(CharacterShared:WaitForChild("CharacterMovementConfig"))
local AnimationSpeedScaling = require(AnimationShared:WaitForChild("AnimationSpeedScaling"))
local DamageService = require(script.Parent.Parent:WaitForChild("combat"):WaitForChild("DamageService"))
local HitEffectService = require(script.Parent.Parent:WaitForChild("combat"):WaitForChild("HitEffectService"))

local MonsterAIService = {}
local started = false
local agents: {[Model]: any} = {}
local random = Random.new()

local THINK_INTERVAL = 0.10
local TARGET_SCAN_INTERVAL = 0.30
local DIRECT_REFRESH_SECONDS = 0.30
local PATH_REFRESH_SECONDS = 0.75
local PATH_TARGET_MOVE_THRESHOLD = 3
local STUCK_CHECK_SECONDS = 0.80
local STUCK_PROGRESS_STUDS = 0.35
local WAYPOINT_TOLERANCE = 1.25
local ATTACK_PURSUIT_STOP_MARGIN = 0.35
local ATTACK_PURSUIT_SPEED_MULTIPLIER = 1.65
local ATTACK_PURSUIT_FOLLOW_GAIN = 5.5
local ATTACK_PURSUIT_MIN_CATCHUP_SPEED = 0.75
local ATTACK_PURSUIT_IDLE_SPEED = 0.08
local ATTACK_PURSUIT_PLAYBACK_EPSILON = 0.02
local ATTACK_ARC_DEGREES = 110
local VERTICAL_TOLERANCE = 5

local function finite(value: any, fallback: number): number
    local n = tonumber(value)
    if n == nil or n ~= n or n == math.huge or n == -math.huge then return fallback end
    return n
end

local function horizontalDelta(left: Vector3, right: Vector3): Vector3
    return Vector3.new(right.X - left.X, 0, right.Z - left.Z)
end

local function horizontalDistance(left: Vector3, right: Vector3): number
    return horizontalDelta(left, right).Magnitude
end

local function rootOf(model: Model?): BasePart?
    if not model then return nil end
    local root = model:FindFirstChild("RootCollider") or model:FindFirstChild("HumanoidRootPart") or model.PrimaryPart
    return if root and root:IsA("BasePart") then root else nil
end

local function navigationRootOf(model: Model): BasePart?
    local root = model:FindFirstChild("HumanoidRootPart")
    return if root and root:IsA("BasePart") then root else rootOf(model)
end

local function targetIsValid(target: Model?): boolean
    return target ~= nil
        and target.Parent ~= nil
        and target:GetAttribute("Damageable") == true
        and tostring(target:GetAttribute("LifeState") or "") == "Alive"
        and rootOf(target) ~= nil
end

local function publishedRows(slug: string, slot: string): {any}
    local profile = MonsterAnimationRegistry.profiles and MonsterAnimationRegistry.profiles[slug]
    local rows = profile and profile.slots and profile.slots[slot]
    local result = {}
    for _, row in ipairs(typeof(rows) == "table" and rows or {}) do
        if tostring(row.animationId or ""):match("^rbxassetid://%d+$") then
            table.insert(result, row)
        end
    end
    return result
end

local function weightedRow(rows: {any}): any?
    local total = 0
    for _, row in ipairs(rows) do total += math.max(1, finite(row.weight, 100)) end
    if total <= 0 then return rows[1] end
    local roll = random:NextNumber(0, total)
    local cursor = 0
    for _, row in ipairs(rows) do
        cursor += math.max(1, finite(row.weight, 100))
        if roll <= cursor then return row end
    end
    return rows[#rows]
end

local function animationPriority(value: any): Enum.AnimationPriority
    local name = tostring(value or "")
    if name == "Idle" then return Enum.AnimationPriority.Idle end
    if name == "Movement" then return Enum.AnimationPriority.Movement end
    if name == "Action2" then return Enum.AnimationPriority.Action2 end
    if name == "Action3" then return Enum.AnimationPriority.Action3 end
    if name == "Action4" then return Enum.AnimationPriority.Action4 end
    return Enum.AnimationPriority.Action
end

local function animatorOf(model: Model): Animator?
    local animator = model:FindFirstChildWhichIsA("Animator", true)
    return if animator and animator:IsA("Animator") then animator else nil
end

local function loadTrack(animator: Animator, row: any, looped: boolean): AnimationTrack?
    local animationId = tostring(row and row.animationId or "")
    if not animationId:match("^rbxassetid://%d+$") then return nil end
    local animation = Instance.new("Animation")
    animation.AnimationId = animationId
    local ok, result = pcall(function() return animator:LoadAnimation(animation) end)
    animation:Destroy()
    if not ok then
        warn("[game1][monster-ai] animation load failed: " .. tostring(result))
        return nil
    end
    local track = result :: AnimationTrack
    track.Looped = looped
    track.Priority = animationPriority(row.priority)
    return track
end

local function stopTrack(track: AnimationTrack?, fade: number?)
    if track and track.IsPlaying then pcall(function() track:Stop(fade or 0.08) end) end
end

local function stopPresentation(agent: any)
    stopTrack(agent.runTrack)
    stopTrack(agent.combatIdleTrack)
    stopTrack(agent.attackTrack)
    agent.attackTrack = nil
end

local function playCombatIdle(agent: any)
    if agent.attacking or not agent.active then return end
    stopTrack(agent.runTrack)
    stopTrack(agent.attackTrack)
    local track = agent.combatIdleTrack
    if track then
        local speed = AnimationSpeedScaling.ResolveScaleForModel(agent.model, "combat_idle")
        if track.IsPlaying then track:AdjustSpeed(speed) else track:Play(0.08, 1, speed) end
    end
    agent.model:SetAttribute("MonsterAnimationState", "combat_idle")
end

local function playRun(agent: any, pursuitMultiplier: number?)
    if agent.attacking then
        -- During active attack the full-body attack keeps ownership. A client
        -- compositor samples Run and writes only the lower-body bones.
        return
    end
    stopTrack(agent.combatIdleTrack)
    stopTrack(agent.attackTrack)
    local track = agent.runTrack
    if track then
        local speed = AnimationSpeedScaling.ResolveScaleForModel(agent.model, "run") * math.max(1, pursuitMultiplier or 1)
        if track.IsPlaying then track:AdjustSpeed(speed) else track:Play(0.08, 1, speed) end
    end
    agent.model:SetAttribute("MonsterAnimationState", "run")
end

local function setState(agent: any, state: string)
    if agent.state == state then return end
    agent.state = state
    agent.model:SetAttribute("MonsterAIState", state)
end

local function clearPath(agent: any)
    if agent.pathBlockedConnection then agent.pathBlockedConnection:Disconnect(); agent.pathBlockedConnection = nil end
    agent.path = nil
    agent.pathWaypoints = nil
    agent.pathIndex = 1
    agent.pathFallbackRequested = false
end

local function stopNavigation(agent: any)
    clearPath(agent)
    agent.navigating = false
    if agent.humanoid.Parent and agent.root.Parent then
        agent.humanoid:Move(Vector3.zero, false)
        agent.humanoid:MoveTo(agent.root.Position)
    end
end

local function runSpeedStuds(agent: any): number
    local runSpeed = math.max(0, finite(agent.model:GetAttribute("RunSpeed"), CharacterMovementConfig.DefaultRunSpeed))
    return CharacterMovementConfig.RobloxSpeed(nil, runSpeed, "Run")
end

local function issueDirectMove(agent: any, destination: Vector3, speed: number)
    clearPath(agent)
    agent.navigationMode = "Direct"
    agent.navigating = true
    agent.lastPathTarget = destination
    agent.nextPathAt = os.clock() + DIRECT_REFRESH_SECONDS
    agent.humanoid.WalkSpeed = math.max(0, speed)
    agent.humanoid.AutoRotate = true
    agent.humanoid:MoveTo(destination)
end

local function rebuildPath(agent: any, destination: Vector3, speed: number)
    clearPath(agent)
    agent.navigationMode = "Path"
    agent.navigating = true
    agent.lastPathTarget = destination
    agent.nextPathAt = os.clock() + PATH_REFRESH_SECONDS
    agent.humanoid.WalkSpeed = math.max(0, speed)
    agent.humanoid.AutoRotate = true
    local path = PathfindingService:CreatePath({AgentRadius = 1, AgentHeight = 4, AgentCanJump = false, WaypointSpacing = 3})
    local ok = pcall(function() path:ComputeAsync(agent.root.Position, destination) end)
    if ok and path.Status == Enum.PathStatus.Success then
        agent.path = path
        agent.pathWaypoints = path:GetWaypoints()
        agent.pathIndex = math.min(2, #agent.pathWaypoints)
        agent.pathBlockedConnection = path.Blocked:Connect(function(blockedIndex)
            if agent.active and blockedIndex >= agent.pathIndex then agent.pathFallbackRequested = true end
        end)
        local waypoint = agent.pathWaypoints[agent.pathIndex]
        if waypoint then agent.humanoid:MoveTo(waypoint.Position) end
    else
        issueDirectMove(agent, destination, speed)
    end
end

local function navigateTo(agent: any, destination: Vector3, speed: number)
    local now = os.clock()
    local progressed = horizontalDistance(agent.lastProgressPosition, agent.root.Position) >= STUCK_PROGRESS_STUDS
    if progressed then
        agent.lastProgressPosition = agent.root.Position
        agent.lastProgressAt = now
    elseif agent.navigating and now - agent.lastProgressAt >= STUCK_CHECK_SECONDS then
        agent.pathFallbackRequested = true
        agent.lastProgressAt = now
    end
    local targetMoved = not agent.lastPathTarget or horizontalDistance(agent.lastPathTarget, destination) >= PATH_TARGET_MOVE_THRESHOLD
    if agent.pathFallbackRequested then
        if agent.navigationMode ~= "Path" or now >= agent.nextPathAt or targetMoved then rebuildPath(agent, destination, speed) end
    elseif not agent.navigating or agent.navigationMode ~= "Direct" or now >= agent.nextPathAt or targetMoved then
        issueDirectMove(agent, destination, speed)
    else
        agent.humanoid.WalkSpeed = math.max(0, speed)
    end
    if agent.navigationMode == "Path" and agent.pathWaypoints then
        local waypoint = agent.pathWaypoints[agent.pathIndex]
        if waypoint and horizontalDistance(agent.root.Position, waypoint.Position) <= WAYPOINT_TOLERANCE then
            agent.pathIndex += 1
            waypoint = agent.pathWaypoints[agent.pathIndex]
            if waypoint then
                agent.humanoid:MoveTo(waypoint.Position)
            else
                agent.pathFallbackRequested = false
                issueDirectMove(agent, destination, speed)
            end
        end
    end
end

local function hasLineOfSight(agent: any, target: Model): boolean
    local targetRoot = rootOf(target)
    if not targetRoot then return false end
    local origin = agent.root.Position + Vector3.new(0, 1, 0)
    local destination = targetRoot.Position + Vector3.new(0, 0.6, 0)
    local params = RaycastParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    params.FilterDescendantsInstances = {agent.model}
    params.IgnoreWater = false
    params.RespectCanCollide = false
    local result = Workspace:Raycast(origin, destination - origin, params)
    return result == nil or result.Instance:IsDescendantOf(target)
end

local function faceDirection(agent: any, direction: Vector3)
    local flat = Vector3.new(direction.X, 0, direction.Z)
    if flat.Magnitude <= 0.001 then return end
    agent.facing = flat.Unit
    if not agent.attackPursuitActive and agent.root.Parent then
        local position = agent.root.Position
        agent.root.CFrame = CFrame.lookAt(position, position + agent.facing, Vector3.yAxis)
    end
end

local function aggressive(agent: any): boolean
    return agent.model:GetAttribute("MonsterAggressive") == true
end
local function aggroRadius(agent: any): number
    return math.max(0, finite(agent.model:GetAttribute("MonsterAggroRadius"), 16))
end
local function attackRadius(agent: any): number
    return math.max(0, finite(agent.model:GetAttribute("MonsterAttackRadius"), 3))
end

local function acquireNearestTarget(agent: any): Model?
    local closest: Model? = nil
    local closestDistance = aggroRadius(agent)
    for _, player in ipairs(Players:GetPlayers()) do
        local character = player.Character
        local targetRoot = rootOf(character)
        if targetIsValid(character) and targetRoot then
            local distance = horizontalDistance(agent.root.Position, targetRoot.Position)
            if distance <= closestDistance then closestDistance = distance; closest = character end
        end
    end
    return closest
end

local function enterCombat(agent: any, target: Model)
    agent.target = target
    agent.model:SetAttribute("MonsterCombatActive", true)
    agent.model:SetAttribute("MonsterTargetName", target.Name)
    local player = Players:GetPlayerFromCharacter(target)
    agent.model:SetAttribute("MonsterTargetUserId", player and player.UserId or 0)
    setState(agent, "Aggro")
end

local function clearAttackPursuit(agent: any)
    if agent.attackPursuitActive then
        agent.humanoid:Move(Vector3.zero, false)
        agent.humanoid.WalkSpeed = 0
        agent.attackPursuitActive = false
        agent.model:SetAttribute("MonsterAttackPursuitActive", false)
    else
        agent.attackPursuitActive = false
    end
end

local function attackPursuitPlaybackSpeed(agent: any, movementMultiplier: number?): number
    return AnimationSpeedScaling.ResolveScaleForModel(agent.model, "run") * math.max(0.01, movementMultiplier or ATTACK_PURSUIT_SPEED_MULTIPLIER)
end

local function publishAttackPursuitPlaybackSpeed(agent: any, movementMultiplier: number?)
    local desired = attackPursuitPlaybackSpeed(agent, movementMultiplier)
    local current = tonumber(agent.model:GetAttribute("MonsterAttackPursuitPlaybackSpeed"))
    if current == nil or math.abs(current - desired) > ATTACK_PURSUIT_PLAYBACK_EPSILON then
        agent.model:SetAttribute("MonsterAttackPursuitPlaybackSpeed", desired)
    end
end

local function leaveCombat(agent: any)
    agent.target = nil
    agent.attacking = false
    agent.attackSerial += 1
    clearAttackPursuit(agent)
    stopNavigation(agent)
    stopPresentation(agent)
    agent.model:SetAttribute("MonsterTargetName", "")
    agent.model:SetAttribute("MonsterTargetUserId", 0)
    agent.model:SetAttribute("MonsterCombatActive", false)
    agent.model:SetAttribute("MonsterAttackPhase", "")
    setState(agent, "Idle")
end

local function pursueDirectlyDuringAttack(agent: any, targetRoot: BasePart): boolean
    local offset = horizontalDelta(agent.root.Position, targetRoot.Position)
    local distance = offset.Magnitude
    local range = attackRadius(agent)
    local preferredDistance = math.max(0, range - ATTACK_PURSUIT_STOP_MARGIN)
    if distance <= 0.001 then
        clearAttackPursuit(agent)
        return false
    end

    local direction = offset.Unit
    local targetVelocity = horizontalDelta(Vector3.zero, targetRoot.AssemblyLinearVelocity)
    local targetRetreatSpeed = math.max(0, targetVelocity:Dot(direction))
    local maximumSpeed = runSpeedStuds(agent) * ATTACK_PURSUIT_SPEED_MULTIPLIER
    local distanceError = math.max(0, distance - preferredDistance)
    local correctionSpeed = distanceError * ATTACK_PURSUIT_FOLLOW_GAIN
    local desiredSpeed = math.min(maximumSpeed, targetRetreatSpeed + correctionSpeed)
    if distance > range then
        desiredSpeed = math.max(desiredSpeed, math.min(maximumSpeed, targetRetreatSpeed + ATTACK_PURSUIT_MIN_CATCHUP_SPEED))
    end

    if desiredSpeed <= ATTACK_PURSUIT_IDLE_SPEED then
        clearAttackPursuit(agent)
        return false
    end

    local enteringPursuit = not agent.attackPursuitActive
    agent.attackPursuitActive = true
    agent.humanoid.WalkSpeed = desiredSpeed
    agent.humanoid.AutoRotate = true
    -- Active-attack pursuit is a continuous velocity command, not a stream of
    -- MoveTo destinations. Reissuing MoveTo around the attack-radius boundary
    -- produces visible stop/catch-up pulses when player and monster speeds are
    -- close. Humanoid:Move keeps one continuous locomotion owner for the attack.
    agent.humanoid:Move(direction, false)
    agent.facing = direction
    if enteringPursuit then
        agent.model:SetAttribute("MonsterAttackPursuitActive", true)
    end
    local baseRunSpeed = math.max(0.001, runSpeedStuds(agent))
    publishAttackPursuitPlaybackSpeed(agent, desiredSpeed / baseRunSpeed)
    return true
end

local function maintainAttackPursuit(agent: any, target: Model, serial: number)
    task.spawn(function()
        while agent.active
            and agent.attacking
            and agent.attackSerial == serial
            and agent.target == target
            and tostring(agent.model:GetAttribute("LifeState") or "") == "Alive" do
            local liveRoot = rootOf(target)
            if not targetIsValid(target) or not liveRoot then
                clearAttackPursuit(agent)
                return
            end
            local pursuing = pursueDirectlyDuringAttack(agent, liveRoot)
            if not pursuing then
                faceDirection(agent, liveRoot.Position - agent.root.Position)
            end
            RunService.Heartbeat:Wait()
        end
    end)
end

local function attackStillConnects(agent: any, target: Model): boolean
    local targetRoot = rootOf(target)
    if not targetIsValid(target) or not targetRoot then return false end
    local delta = horizontalDelta(agent.root.Position, targetRoot.Position)
    if delta.Magnitude > attackRadius(agent) or math.abs(targetRoot.Position.Y - agent.root.Position.Y) > VERTICAL_TOLERANCE then return false end
    if delta.Magnitude > 0.001 then
        if agent.facing:Dot(delta.Unit) < math.cos(math.rad(ATTACK_ARC_DEGREES * 0.5)) then return false end
    end
    return hasLineOfSight(agent, target)
end

local function beginAttack(agent: any, target: Model)
    if agent.attacking or os.clock() < agent.nextAttackAt then return end
    local row = weightedRow(agent.attackRows)
    if not row then return end
    local percent = AnimationSpeedScaling.ResolveForModel(agent.model, "attack")
    local timing = AttackTimelineConfig.ResolveRuntime(row.clipId, percent, row.duplicateFirstFrameAtEnd == true)
    if not timing then return end

    agent.attacking = true
    agent.attackSerial += 1
    local serial = agent.attackSerial
    local duration = math.max(0.05, finite(timing.duration, 0.05))
    local now = os.clock()
    agent.attackEndsAt = now + duration
    agent.nextAttackAt = agent.attackEndsAt
    setState(agent, "Attack")
    stopNavigation(agent)
    stopTrack(agent.runTrack)
    stopTrack(agent.combatIdleTrack)
    stopTrack(agent.attackTrack)
    agent.attackTrack = loadTrack(agent.animator, row, false)
    if agent.attackTrack then agent.attackTrack:Play(0.05, 1, math.max(0.01, percent / 100)) end
    agent.model:SetAttribute("MonsterAnimationState", "attack")
    agent.model:SetAttribute("AnimationPlaybackSpeedPercent", percent)
    agent.model:SetAttribute("MonsterAttackClipId", tostring(row.clipId or ""))
    agent.model:SetAttribute("MonsterAttackPhase", "Windup")
    local targetRoot = rootOf(target)
    if targetRoot then faceDirection(agent, targetRoot.Position - agent.root.Position) end
    maintainAttackPursuit(agent, target, serial)

    local hit = timing.events and timing.events.Hit
    local hitTime = math.max(0, finite(hit and hit.time, duration * 0.5))
    task.delay(hitTime, function()
        if not agent.active or agent.attackSerial ~= serial or agent.target ~= target or tostring(agent.model:GetAttribute("LifeState") or "") ~= "Alive" then return end
        local liveRoot = rootOf(target)
        if liveRoot then
            local direction = liveRoot.Position - agent.root.Position
            local flatDirection = horizontalDelta(Vector3.zero, direction)
            if flatDirection.Magnitude > 0.001 then agent.facing = flatDirection.Unit end
            if not agent.attackPursuitActive then faceDirection(agent, direction) end
        end
        if attackStillConnects(agent, target) then
            local damage, killed = DamageService.Apply(agent.model, target, finite(agent.model:GetAttribute("Damage"), 0))
            HitEffectService.Publish(agent.model, target, target:GetAttribute("LastCritical") == true, rootOf(target) and rootOf(target).Position or nil)
            agent.model:SetAttribute("LastMonsterAttackDamage", damage)
            agent.model:SetAttribute("MonsterAttackPhase", if damage > 0 then "Hit" else "Miss")
            if killed then clearAttackPursuit(agent) end
        else
            agent.model:SetAttribute("LastMonsterAttackDamage", 0)
            agent.model:SetAttribute("MonsterAttackPhase", "Miss")
        end
    end)

    task.delay(duration, function()
        if not agent.active or agent.attackSerial ~= serial then return end
        agent.attacking = false
        agent.attackEndsAt = 0
        clearAttackPursuit(agent)
        stopTrack(agent.attackTrack)
        agent.attackTrack = nil
        if agent.target == target and targetIsValid(target) and aggressive(agent) then
            agent.model:SetAttribute("MonsterAttackPhase", "Cooldown")
            playCombatIdle(agent)
        end
    end)
end

local function updateTarget(agent: any, now: number)
    if agent.target and targetIsValid(agent.target) then return end
    if agent.target then leaveCombat(agent) end
    if not aggressive(agent) or now < agent.nextTargetScanAt then return end
    agent.nextTargetScanAt = now + TARGET_SCAN_INTERVAL
    local target = acquireNearestTarget(agent)
    if target then enterCombat(agent, target) end
end

local function runAgent(agent: any)
    task.wait(random:NextNumber(0, THINK_INTERVAL))
    while agent.active and agent.model.Parent do
        task.wait(THINK_INTERVAL)
        if tostring(agent.model:GetAttribute("LifeState") or "") ~= "Alive" then
            leaveCombat(agent)
            break
        end
        if not aggressive(agent) then
            if agent.target or agent.model:GetAttribute("MonsterCombatActive") == true then leaveCombat(agent) end
            continue
        end
        local now = os.clock()
        updateTarget(agent, now)
        local target = agent.target
        local targetRoot = rootOf(target)
        if target and targetRoot then
            local distance = horizontalDistance(agent.root.Position, targetRoot.Position)
            if agent.attacking then
                -- Active-attack movement is owned by maintainAttackPursuit().
                -- The slower AI decision loop must not issue competing MoveTo calls.
                setState(agent, "Attack")
            elseif distance <= attackRadius(agent) then
                stopNavigation(agent)
                faceDirection(agent, targetRoot.Position - agent.root.Position)
                playCombatIdle(agent)
                beginAttack(agent, target)
            else
                setState(agent, "Chase")
                clearAttackPursuit(agent)
                playRun(agent)
                navigateTo(agent, targetRoot.Position, runSpeedStuds(agent))
            end
        elseif agent.model:GetAttribute("MonsterCombatActive") == true then
            leaveCombat(agent)
        end
    end
    agent.active = false
end

local function bindMonster(model: Model)
    if agents[model] then return end
    task.spawn(function()
        local deadline = os.clock() + 5
        while model.Parent and model:GetAttribute("Game1MonsterRuntime") ~= true and os.clock() < deadline do
            task.wait(0.03)
        end
        if not model.Parent or model:GetAttribute("Game1MonsterRuntime") ~= true or agents[model] then return end
        local root = navigationRootOf(model) or model:WaitForChild("HumanoidRootPart", 5)
        local humanoid = model:FindFirstChildOfClass("Humanoid") or model:WaitForChild("Humanoid", 5)
        local animator = animatorOf(model)
        if not root or not root:IsA("BasePart") or not humanoid or not humanoid:IsA("Humanoid") or not animator then return end
        local slug = string.lower(tostring(model:GetAttribute("MonsterSlug") or ""))
        local runRow = publishedRows(slug, "run")[1] or publishedRows(slug, "walk")[1]
        local combatIdleRow = publishedRows(slug, "combat_idle")[1] or publishedRows(slug, "idle")[1]
        local attackRows = publishedRows(slug, "attack")
        if #attackRows == 0 then
            warn("[game1][monster-ai] no published attack animation for " .. slug)
        end
        local agent = {
            model = model,
            root = root,
            humanoid = humanoid,
            animator = animator,
            attackRows = attackRows,
            runTrack = runRow and loadTrack(animator, runRow, true) or nil,
            combatIdleTrack = combatIdleRow and loadTrack(animator, combatIdleRow, true) or nil,
            attackTrack = nil,
            target = nil,
            active = true,
            attacking = false,
            attackSerial = 0,
            attackEndsAt = 0,
            nextAttackAt = 0,
            nextTargetScanAt = 0,
            attackPursuitActive = false,
            facing = root.CFrame.LookVector,
            state = "Idle",
            navigating = false,
            navigationMode = "",
            nextPathAt = 0,
            lastPathTarget = nil,
            path = nil,
            pathWaypoints = nil,
            pathIndex = 1,
            pathBlockedConnection = nil,
            pathFallbackRequested = false,
            lastProgressPosition = root.Position,
            lastProgressAt = os.clock(),
        }
        agents[model] = agent
        if runRow then
            model:SetAttribute("MonsterRunAnimationId", tostring(runRow.assetId or tostring(runRow.animationId):match("(%d+)$") or ""))
            model:SetAttribute("MonsterAnimationPhase", random:NextNumber(0, 0.999))
            publishAttackPursuitPlaybackSpeed(agent, ATTACK_PURSUIT_SPEED_MULTIPLIER)
        end
        model:SetAttribute("MonsterAttackPursuitActive", false)
        model:SetAttribute("MonsterAIState", "Idle")
        model:GetAttributeChangedSignal("LifeState"):Connect(function()
            if agents[model] == agent and tostring(model:GetAttribute("LifeState") or "") ~= "Alive" then
                agent.attackSerial += 1
                agent.attacking = false
                agent.target = nil
                clearAttackPursuit(agent)
                stopNavigation(agent)
                stopPresentation(agent)
                model:SetAttribute("MonsterCombatActive", false)
            end
        end)
        model.Destroying:Connect(function()
            if agents[model] == agent then
                agent.active = false
                clearPath(agent)
                agents[model] = nil
            end
        end)
        task.spawn(runAgent, agent)
    end)
end

local function bindFolder(folder: Folder)
    for _, child in ipairs(folder:GetChildren()) do if child:IsA("Model") then bindMonster(child) end end
    folder.ChildAdded:Connect(function(child) if child:IsA("Model") then task.defer(bindMonster, child) end end)
end

function MonsterAIService.Start()
    if started then return end
    started = true
    local folder = Workspace:FindFirstChild("Monsters")
    if folder and folder:IsA("Folder") then bindFolder(folder) end
    Workspace.ChildAdded:Connect(function(child)
        if child.Name == "Monsters" and child:IsA("Folder") then bindFolder(child) end
    end)
    print("[game1][monster-ai] RobloxLineage aggro/chase/attack-pursuit runtime ready")
end

return table.freeze(MonsterAIService)
