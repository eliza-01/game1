-- M91: authoritative wander/locomotion lifecycle; RNG and animation policy are injected.
-- No dependency on MonsterSpawnerService (population remains owned by spawner).
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CharacterMovementConfig = require(Shared:WaitForChild("character"):WaitForChild("CharacterMovementConfig"))
local MonsterSpawnGeometry = require(script.Parent:WaitForChild("MonsterSpawnGeometry"))

local MonsterWanderController = {}

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

function MonsterWanderController.new(spawnRandom: Random, spawnGeometry: any, presentation: any): any
    local stopTrack = presentation.stopTrack
    local stopIdleState = presentation.stopIdleState
    local playBaseIdle = presentation.playBaseIdle
    local playCombatIdleState = presentation.playCombatIdleState
    local playTrackAtConfiguredSpeed = presentation.playTrackAtConfiguredSpeed

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
        -- Stop a previous MoveToFinished observer promptly on combat/death/release.
        entry.wanderGeneration = (entry.wanderGeneration or 0) + 1
        if entry.wanderMoveConnection then
            entry.wanderMoveConnection:Disconnect()
            entry.wanderMoveConnection = nil
        end
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
        entry.wanderThread = task.spawn(function()
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

                local moveGeneration = entry.wanderGeneration or 0
                local finished = false
                local moveConnection = humanoid.MoveToFinished:Connect(function()
                    finished = true
                end)
                entry.wanderMoveConnection = moveConnection
                local nextRefresh = os.clock() + WANDER_MOVE_REFRESH_SECONDS
                while not finished
                    and entry.wanderGeneration == moveGeneration
                    and state.instances[model] == entry
                    and model.Parent
                    and not entry.dying
                    and model:GetAttribute("MonsterCombatActive") ~= true
                    and model:GetAttribute("InCombat") ~= true
                    and os.clock() < (entry.wanderDeadline or math.huge)
                do
                    task.wait(0.1)
                    if entry.wanderGeneration ~= moveGeneration or state.instances[model] ~= entry then
                        break
                    end
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
                if entry.wanderMoveConnection == moveConnection then
                    entry.wanderMoveConnection = nil
                end

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


    local controller = {}
    function controller:Start(state: any, model: Model, entry: any)
        startWanderLoop(state, model, entry)
    end
    function controller:Refresh(model: Model, entry: any)
        refreshWanderLocomotion(model, entry)
    end
    function controller:Stop(entry: any)
        stopWanderMovement(entry)
    end
    function controller:Dispose(entry: any)
        stopWanderMovement(entry)
        -- The task may be inside its initial delay or between wander attempts.
        -- Cancellation is reserved for final release; combat pauses never cancel it.
        local thread = entry.wanderThread
        entry.wanderThread = nil
        if thread and coroutine.status(thread) ~= "dead" then
            pcall(task.cancel, thread)
        end
    end
    return table.freeze(controller)
end

return table.freeze(MonsterWanderController)
