-- Server-authoritative NPC combat: player aggro, pursuit and distance-based attacks.
-- Equipment and weapon volumes are presentation only; hit validation uses the
-- same range/line-of-sight + DamageService contract as monster attacks.
-- A single scheduler updates all agents, rather than one unbounded loop per NPC.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local NpcRegistry = require(Shared:WaitForChild("npc"):WaitForChild("NpcRegistry"))
local NpcAnimationRegistry = require(Shared:WaitForChild("npc"):WaitForChild("NpcAnimationRegistry"))
local AnimationSpeedScaling = require(Shared:WaitForChild("animation"):WaitForChild("AnimationSpeedScaling"))
local CharacterMovementConfig = require(Shared:WaitForChild("character"):WaitForChild("CharacterMovementConfig"))
local AttackTimelineConfig = require(Shared:WaitForChild("combat"):WaitForChild("AttackTimelineConfig"))
local WeightedAnimationChoice = require(Shared:WaitForChild("animation"):WaitForChild("WeightedAnimationChoice"))
local DamageService = require(script.Parent.Parent:WaitForChild("combat"):WaitForChild("DamageService"))
local DamageSignals = require(script.Parent.Parent:WaitForChild("combat"):WaitForChild("ActorDamageSignals"))
local HitEffectService = require(script.Parent.Parent:WaitForChild("combat"):WaitForChild("HitEffectService"))
local CombatStateService = require(script.Parent.Parent:WaitForChild("combat"):WaitForChild("CombatStateService"))
local Navigator = require(script.Parent.Parent:WaitForChild("actor"):WaitForChild("ActorChaseNavigator"))
local Queries = require(script.Parent.Parent:WaitForChild("actor"):WaitForChild("ActorCombatTargeting"))
local Tracks = require(script.Parent:WaitForChild("NpcAnimationTracks"))
local WeaponAttackMovement = require(Shared:WaitForChild("weapon"):WaitForChild("WeaponAttackMovement"))
local Facing = require(script.Parent.Parent:WaitForChild("actor"):WaitForChild("ActorFacingTracker"))
local AttackPursuit = require(script.Parent.Parent:WaitForChild("actor"):WaitForChild("ActorAttackPursuit"))

local NpcCombatAIService = {}
local agents: {[Model]: any} = {}
local started = false
local rng = Random.new()
local TICK_SECONDS = 0.1
-- Roblox resolves AnimationTrack.Length asynchronously for freshly loaded clips.
local CLIP_LENGTH_RESOLVE_TIMEOUT = 3
local VERTICAL_TOLERANCE = 5
local HIT_ARC_COSINE = math.cos(math.rad(55)) -- same 110-degree hit arc as monsters

local function finite(value: any, fallback: number): number
    local v = tonumber(value)
    return if v and v == v and v ~= math.huge and v ~= -math.huge then v else fallback
end

local function setState(agent: any, name: string)
    if agent.state == name then return end
    agent.state = name
    agent.model:SetAttribute("NpcAIState", name)
end

local function stopAttack(agent: any)
    Facing.Stop(agent.model)
    agent.pursuit:Stop()
    agent.pursuitMoving = false
    agent.model:SetAttribute("NpcAttackPursuitActive", false)
    if agent.attacking then
        agent.serial += 1 -- invalidate pending timed hit and completion callbacks
        agent.attacking = false
        agent.presentation.EndAttack()
        agent.currentAttackTrack = nil
        agent.currentAttackRow = nil
    end
end

-- Home is an authored spawn pose, not the last combat position.
-- Pin stationary NPCs so walking players cannot physically shove shopkeepers.
local function pinAtRest(agent: any, pin: boolean)
    if agent.root.Anchored == pin then return end
    if pin then
        agent.root.AssemblyLinearVelocity = Vector3.zero
        agent.root.AssemblyAngularVelocity = Vector3.zero
    end
    agent.root.Anchored = pin
    if not pin then pcall(function() agent.root:SetNetworkOwner(nil) end) end
end

local function clearTarget(agent: any)
    stopAttack(agent)
    agent.navigator:Stop()
    agent.presentation.SetCombatMoving(false)
    agent.presentation.SetReturnMoving(false)
    agent.presentation.SetCombatActive(false)
    agent.target = nil
    agent.model:SetAttribute("NpcTargetUserId", 0)
    if agent.model.Parent then CombatStateService.Clear(agent.model) end
end

local function startReturn(agent: any, targetKilled: boolean)
    -- Mark the entire return lifecycle BEFORE clearing combat. Otherwise the
    -- InCombat change briefly reactivates idle_special during ReturnWait.
    agent.presentation.SetReturnActive(true)
    clearTarget(agent)
    -- Only killing/losing a dead target waits; a pursuit leash break returns now.
    local halfSteps = math.max(0, math.floor(agent.returnDelaySeconds * 2 + 0.0001))
    agent.returnAt = os.clock() + (if targetKilled then rng:NextInteger(0, halfSteps) / 2 else 0)
    agent.model:SetAttribute("NpcReturnAt", agent.returnAt)
    setState(agent, "ReturnWait")
    pinAtRest(agent, true)
end

local function enterCombat(agent: any, target: Model)
    clearTarget(agent)
    agent.returnAt = 0
    agent.target = target
    pinAtRest(agent, false)
    local player = game:GetService("Players"):GetPlayerFromCharacter(target)
    agent.model:SetAttribute("NpcTargetUserId", if player then player.UserId else 0)
    setState(agent, "Chase")
    CombatStateService.Activate(agent.model)
    agent.presentation.SetCombatActive(true)
    agent.presentation.SetReturnActive(false)
end

local function returnHome(agent: any, now: number)
    if now < agent.returnAt then
        setState(agent, "ReturnWait")
        agent.presentation.SetReturnMoving(false)
        pinAtRest(agent, true)
        return
    end
    local distance = Queries.Distance(agent.root.Position, agent.home.Position)
    if distance <= 0.8 then
        agent.navigator:Stop()
        -- Snap only at navigation tolerance, restoring the exact authored yaw.
        agent.root.CFrame = agent.home
        agent.presentation.SetReturnMoving(false)
        setState(agent, "Idle")
        pinAtRest(agent, true)
        agent.presentation.SetReturnActive(false)
        return
    end
    pinAtRest(agent, false)
    setState(agent, "Return")
    agent.presentation.SetReturnMoving(true)
    local speed = CharacterMovementConfig.RobloxSpeed(nil, agent.model:GetAttribute("RunSpeed"), "Run")
    agent.navigator:Chase(agent.home.Position, speed)
end

local function attackCanConnect(agent: any, target: Model): boolean
    local targetRoot = Queries.Root(target)
    if not Queries.Valid(target) or not targetRoot then return false end
    local origin = agent.root.Position
    if math.abs(targetRoot.Position.Y - origin.Y) > VERTICAL_TOLERANCE then return false end
    if Queries.Distance(origin, targetRoot.Position) > agent.attackRadius then return false end
    local direction = Vector3.new(targetRoot.Position.X - origin.X, 0, targetRoot.Position.Z - origin.Z)
    if direction.Magnitude > 0.01 and agent.root.CFrame.LookVector:Dot(direction.Unit) < HIT_ARC_COSINE then return false end
    return Queries.Visible(agent.model, origin + Vector3.new(0, 0.6, 0), target)
end

-- Damage events are independent from the authored animation playback.
-- One looped attack track owns the entire in-range engagement, while the
-- AI schedules one hit per loop and handles return/chase only at boundaries.
local function attackTiming(agent: any, row: any?, percent: number, track: AnimationTrack?): (number, number)
    local timeline = row and AttackTimelineConfig.ResolveRuntime(row.clipId, percent) or nil
    local speed = math.max(0.01, percent / 100)
    local length = if track then finite(track.Length, 0) else 0
    if track and length <= 0 and not timeline then
        local deadline = os.clock() + CLIP_LENGTH_RESOLVE_TIMEOUT
        repeat
            task.wait(0.05)
            length = finite(track.Length, 0)
        until length > 0 or os.clock() >= deadline or not agent.active or not agent.attacking
    end
    -- This is the actual repeating animation period, NOT its tail guard.
    -- Hit is an event INSIDE the cycle and never interrupts the track.
    local duration = if length > 0 then length / speed
        elseif timeline then timeline.playbackDuration
        else math.clamp(1.2 / speed, 0.25, 5)
    duration = math.max(0.05, duration)
    local hit = timeline and timeline.events and timeline.events.Hit
    local hitAt = if hit then math.clamp(finite(hit.normalizedTime, 0.5) * duration, 0, duration)
        else duration * 0.5
    return duration, hitAt
end

local function attackReady(agent: any, target: Model): boolean
    local targetRoot = Queries.Root(target)
    if not targetRoot or not Queries.Valid(target) then return false end
    if Queries.Distance(agent.home.Position, targetRoot.Position) > agent.pursuitRadius then return false end
    local origin = agent.root.Position
    return Queries.Distance(origin, targetRoot.Position) <= agent.attackRadius
        and math.abs(origin.Y - targetRoot.Position.Y) <= VERTICAL_TOLERANCE
        and Queries.Visible(agent.model, origin + Vector3.new(0, 0.6, 0), target)
end

local function beginAttack(agent: any, target: Model, continuing: boolean?)
    if agent.attacking or (not continuing and os.clock() < agent.nextAttackAt) then return end
    local row
    if continuing then
        row = agent.currentAttackRow
    else
        local weightedRows = {}
        for _, candidate in ipairs(agent.attackRows) do
            table.insert(weightedRows, { row = candidate })
        end
        local selection = WeightedAnimationChoice.Select(weightedRows, rng)
        row = selection and selection.row or nil
        agent.currentAttackRow = row
    end
    local scaling = AnimationSpeedScaling.ResolveDetailsForModel(agent.model, "attack")
    local percent = if scaling.hasRule then scaling.percent
        else math.clamp(finite(agent.model:GetAttribute("AttackSpeed"), 100), 1, 400)

    agent.attacking = true
    agent.serial += 1
    local serial = agent.serial
    local beganAt = os.clock()
    if not continuing then
        agent.navigator:Stop()
        agent.presentation.SetCombatMoving(false)
        setState(agent, "Attack")
        agent.model:SetAttribute("NpcAttackClipId", if row then tostring(row.clipId or "") else "")
    end
    Facing.Track(agent.model, agent.root, agent.humanoid, target, Queries.Root)
    agent.model:SetAttribute("NpcAttackPhase", "Windup")
    local track
    if continuing then
        -- Do not stop/restart the track or insert combat_idle between hits.
        agent.presentation.ContinueAttack(percent)
        track = agent.currentAttackTrack
    else
        local _, startedTrack = agent.presentation.StartAttack(row, percent)
        track = startedTrack
        agent.currentAttackTrack = track
    end

    task.spawn(function()
        local duration, hitAt = attackTiming(agent, row, percent, track)
        if not agent.active or agent.serial ~= serial or not agent.attacking then return end
        local elapsed = os.clock() - beganAt
        agent.nextAttackAt = beganAt + duration
        task.delay(math.max(0, hitAt - elapsed), function()
            if not agent.active or agent.serial ~= serial or agent.target ~= target
                or agent.model:GetAttribute("LifeState") ~= "Alive" then return end
            if attackCanConnect(agent, target) then
                local amount, killed = DamageService.Apply(agent.model, target, finite(agent.model:GetAttribute("Damage"), 0))
                agent.model:SetAttribute("NpcLastAttackDamage", amount)
                agent.model:SetAttribute("NpcAttackPhase", if amount > 0 then "Hit" else "Miss")
                if amount > 0 then
                    local targetRoot = Queries.Root(target)
                    HitEffectService.Publish(agent.model, target, target:GetAttribute("LastCritical") == true,
                        if targetRoot then targetRoot.Position else nil)
                end
                if killed then agent.returnAfterAttack = true end
            else
                agent.model:SetAttribute("NpcLastAttackDamage", 0)
                agent.model:SetAttribute("NpcAttackPhase", "Miss")
            end
        end)
        task.delay(math.max(0, duration - elapsed), function()
            if not agent.active or agent.serial ~= serial then return end
            agent.attacking = false
            local killed = agent.returnAfterAttack == true or not Queries.Valid(target)
            agent.returnAfterAttack = false
            if killed then
                Facing.Stop(agent.model)
                agent.pursuit:Stop()
                agent.pursuitMoving = false
                agent.model:SetAttribute("NpcAttackPursuitActive", false)
                agent.presentation.EndAttack()
                agent.currentAttackTrack = nil
                agent.currentAttackRow = nil
                startReturn(agent, true)
            elseif agent.target == target and attackReady(agent, target) then
                -- Another damage cycle, SAME action state and looped animation.
                -- An animation never fades to combat_idle while in hit range.
                beginAttack(agent, target, true)
            else
                Facing.Stop(agent.model)
                agent.pursuit:Stop()
                agent.pursuitMoving = false
                agent.model:SetAttribute("NpcAttackPursuitActive", false)
                agent.presentation.EndAttack()
                agent.currentAttackTrack = nil
                agent.currentAttackRow = nil
                setState(agent, "Aggro")
            end
        end)
    end)
end

local function tickAgent(agent: any, now: number)
    if not agent.model.Parent or agent.model:GetAttribute("LifeState") ~= "Alive" then return end
    if not agent.retaliate then
        if agent.target then startReturn(agent, false) end
        return
    end
    -- A running attack owns its lifecycle until the clip completes, even if
    -- the Hit event kills the target or another player damages this NPC.
    if agent.attacking then return end
    local target = agent.target
    if target then
        local targetRoot = Queries.Root(target)
        if not targetRoot or not Queries.Valid(target) then
            startReturn(agent, true)
            target = nil
        elseif Queries.Distance(agent.home.Position, targetRoot.Position) > agent.pursuitRadius then
            startReturn(agent, false)
            target = nil
        end
    end
    if not target then
        if agent.state ~= "Idle" then returnHome(agent, now) end
        return
    end
    if agent.model:GetAttribute("InCombat") ~= true then
        agent.model:SetAttribute("InCombat", true)
        agent.model:SetAttribute("CombatState", "Combat")
    end
    if agent.attacking then return end
    local targetRoot = Queries.Root(target)
    if not targetRoot then startReturn(agent, true); return end
    if attackReady(agent, target) then
        agent.navigator:Stop()
        agent.presentation.SetCombatMoving(false)
        setState(agent, "AttackReady")
        beginAttack(agent, target)
    else
        setState(agent, "Chase")
        agent.presentation.SetCombatMoving(true)
        local speed = CharacterMovementConfig.RobloxSpeed(nil, agent.model:GetAttribute("RunSpeed"), "Run")
        agent.navigator:Chase(targetRoot.Position, speed)
    end
end

local function onDamage(attacker: Model?, target: Model, attempted: number)
    local agent = agents[target]
    if not agent or not agent.active or not agent.retaliate
        or agent.model:GetAttribute("LifeState") ~= "Alive" or attempted <= 0 then return end
    if not attacker or not game:GetService("Players"):GetPlayerFromCharacter(attacker) then return end
    local root = Queries.Root(attacker)
    if root and Queries.Valid(attacker)
        and Queries.Distance(agent.home.Position, root.Position) <= agent.pursuitRadius
        and agent.attackRadius > 0 then
        -- Preserve an in-flight attack, like the monster attack owner does.
        -- Repeated strikes from the same player must not reset its animation.
        if agent.attacking then return end
        if agent.target == attacker then return end
        enterCombat(agent, attacker)
    end
end

function NpcCombatAIService.Bind(model: Model, root: BasePart, presentation: any)
    local existing = agents[model]
    if existing then return end
    local humanoid = model:FindFirstChildOfClass("Humanoid")
    if not humanoid then return end
    local definition = (NpcRegistry.npcs or {})[tostring(model:GetAttribute("NpcSlug") or "")]
    local behavior = definition and definition.behavior or {}
    local retaliate = behavior.retaliateWhenAttacked == true
    local pursuitRadius = math.max(0, finite(behavior.pursuitRadiusStuds, 16))
    local attackRadius = math.max(0, finite(behavior.attackRadiusStuds, 3))
    local returnDelaySeconds = math.clamp(finite(behavior.returnDelaySeconds, 10), 0, 600)
    local profile = (NpcAnimationRegistry.profiles or {})[tostring(model:GetAttribute("NpcSlug") or "")]
    local weaponSet = tostring(model:GetAttribute("NpcWeaponSet") or "1hs")
    local policy = WeaponAttackMovement.Resolve(model:GetAttribute("NpcWeaponType"))
    local home = root.CFrame
    local agent = {
        model = model, root = root, humanoid = humanoid, presentation = presentation,
        navigator = Navigator.new(root, humanoid), pursuit = AttackPursuit.new(root, humanoid),
        policy = policy, target = nil, state = "Idle",
        retaliate = retaliate, pursuitRadius = pursuitRadius, attackRadius = attackRadius,
        returnDelaySeconds = returnDelaySeconds, returnAt = 0, home = home,
        attackRows = Tracks.PublishedRows(profile, "attack", weaponSet),
        attacking = false, active = true, serial = 0, nextAttackAt = 0,
        returnAfterAttack = false, currentAttackRow = nil, currentAttackTrack = nil,
    }
    agents[model] = agent
    model:SetAttribute("NpcAIState", "Idle")
    model:SetAttribute("NpcTargetUserId", 0)
    model:SetAttribute("NpcAttackPhase", "")
    model:SetAttribute("NpcRetaliateWhenAttacked", retaliate)
    model:SetAttribute("NpcPursuitRadius", pursuitRadius)
    model:SetAttribute("NpcReturnDelayMaxSeconds", returnDelaySeconds)
    model:SetAttribute("NpcAttackRadius", attackRadius)
    model:SetAttribute("NpcAttackPursuitActive", false)
    model:SetAttribute("NpcAttackPursuitMode", policy.locomotionMode)
    model:SetAttribute("NpcAttackPursuitAnimationId", "")
    model:SetAttribute("NpcAttackPursuitPlaybackSpeed", 1)
    model:SetAttribute("NpcAttackPursuitPhase", rng:NextNumber(0, 0.999))
    local movementSlot = string.lower(policy.locomotionMode)
    local rows = Tracks.PublishedRows(profile, movementSlot, weaponSet)
    if #rows == 0 then
        movementSlot = if movementSlot == "walk" then "run" else "walk"
        rows = Tracks.PublishedRows(profile, movementSlot, weaponSet)
    end
    agent.pursuitChannel = movementSlot
    local row = rows[1]
    if row then
        model:SetAttribute("NpcAttackPursuitAnimationId", tostring(row.assetId or tostring(row.animationId):match("(%d+)$") or ""))
    end
    pinAtRest(agent, true)
end

function NpcCombatAIService.Unbind(model: Model)
    local agent = agents[model]
    if not agent then return end
    agent.active = false
    agent.serial += 1
    Facing.Stop(agent.model)
    agent.pursuit:Stop()
    agent.navigator:Destroy()
    agents[model] = nil
    -- Do not call presentation methods after its lifecycle has been disposed.
end

function NpcCombatAIService.Start()
    if started then return end
    started = true
    DamageSignals.Event:Connect(onDamage)
    local elapsed = 0
    RunService.Heartbeat:Connect(function(dt)
        -- Monster-style movement during an attack is independent from the
        -- slower AI decision cadence and never restarts the animation track.
        for _, agent in pairs(agents) do
            if agent.active and agent.attacking then
                local target = agent.target
                local targetRoot = if target and Queries.Valid(target) then Queries.Root(target) else nil
                local inLeash = targetRoot and Queries.Distance(agent.home.Position, targetRoot.Position) <= agent.pursuitRadius
                local allowed = targetRoot and inLeash and agent.model:GetAttribute("LifeState") == "Alive"
                if allowed then
                    local stat = agent.model:GetAttribute("RunSpeed")
                    local maxSpeed = CharacterMovementConfig.RobloxSpeedAtRunMultiplier(nil, stat, agent.policy.runSpeedMultiplier)
                    local moving, speed = agent.pursuit:Step(targetRoot, agent.attackRadius, maxSpeed)
                    if moving ~= agent.pursuitMoving then
                        agent.pursuitMoving = moving
                        agent.model:SetAttribute("NpcAttackPursuitActive", moving)
                    end
                    if moving then
                        local equivalent = CharacterMovementConfig.EquivalentRunSpeedForLocomotion(
                            stat, speed / math.max(0.001, CharacterMovementConfig.RobloxSpeed(nil, stat, "Run")), agent.pursuitChannel == "walk" and "Walk" or "Run")
                        local scale = AnimationSpeedScaling.ResolveForModelWithStatValue(
                            agent.model, agent.pursuitChannel, equivalent) / 100
                        local old = tonumber(agent.model:GetAttribute("NpcAttackPursuitPlaybackSpeed")) or 0
                        if math.abs(scale - old) >= 0.025 then agent.model:SetAttribute("NpcAttackPursuitPlaybackSpeed", scale) end
                    end
                else
                    agent.pursuit:Stop()
                    if agent.pursuitMoving then
                        agent.pursuitMoving = false
                        agent.model:SetAttribute("NpcAttackPursuitActive", false)
                    end
                end
            end
        end
        elapsed += dt
        if elapsed < TICK_SECONDS then return end
        elapsed %= TICK_SECONDS
        local now = os.clock()
        for _, agent in pairs(agents) do
            if agent.active then tickAgent(agent, now) end
        end
    end)
end

return table.freeze(NpcCombatAIService)
