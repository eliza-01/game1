-- Original M94 chase/path navigation, extracted without algorithm changes in M104.
-- Owns only general Chase navigation; the authored attack pursuit lives in
-- ActorAttackPursuit via MonsterAttackExecutor, and Wander has its own controller.
local Budget = require(script.Parent.Parent:WaitForChild("actor"):WaitForChild("NavigationScheduler"))
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CharacterMovementConfig = require(Shared:WaitForChild("character"):WaitForChild("CharacterMovementConfig"))
local TargetPolicy = require(script.Parent:WaitForChild("MonsterTargetPolicy"))
local horizontalDistance = TargetPolicy.HorizontalDistance

local MonsterChaseNavigation = {}

local DIRECT_REFRESH_SECONDS = 0.30
local PATH_REFRESH_SECONDS = 0.75
local PATH_TARGET_MOVE_THRESHOLD = 3
local STUCK_CHECK_SECONDS = 0.80
local STUCK_PROGRESS_STUDS = 0.35
local WAYPOINT_TOLERANCE = 1.25

local function finite(value: any, fallback: number): number
    local n = tonumber(value)
    if n == nil or n ~= n or n == math.huge or n == -math.huge then return fallback end
    return n
end

local function clearPath(agent: any)
    if agent.pathBlockedConnection then agent.pathBlockedConnection:Disconnect(); agent.pathBlockedConnection = nil end
    Budget.Cancel(agent.pathRequest)
    agent.pathRequest = nil
    agent.pathRequestTarget = nil
    if agent.path then agent.path:Destroy() end
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
    local runSpeed = math.max(0, finite(agent.model:GetAttribute("RunSpeed"), CharacterMovementConfig.DefaultRunSpeed) + finite(agent.model:GetAttribute("SkillRunSpeedBonus"), 0))
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
    agent.pathRequestTarget = agent.target
    agent.pathRequestReturning = agent.returning
    agent.pathRequest = Budget.Request(agent, agent.root, destination)
    -- No new MoveTo while admission/ComputeAsync is pending. The periodic AI
    -- still owns attack, return and target checks; waiting is not stuck time.
    agent.humanoid:MoveTo(agent.root.Position)
    agent.lastProgressPosition = agent.root.Position
    agent.lastProgressAt = os.clock()
    if not agent.pathRequest then
        -- A cancelled, still-running native request retains its owner slot.
        agent.pathFallbackRequested = true
        agent.nextPathAt = 0
    end
end

local function consumePath(agent, destination, speed)
    local ticket = agent.pathRequest
    if not ticket then return false end
    if agent.pathRequestTarget ~= agent.target or agent.pathRequestReturning ~= agent.returning then
        rebuildPath(agent, destination, speed)
        return true
    end
    Budget.UpdateQueued(ticket, destination)
    agent.lastPathTarget = ticket.destination
    agent.humanoid.WalkSpeed = math.max(0, speed)
    local ready, result = Budget.Take(ticket)
    if not ready then
        agent.lastProgressPosition = agent.root.Position
        agent.lastProgressAt = os.clock()
        return true
    end
    agent.pathRequest = nil
    agent.pathRequestTarget = nil
    if Budget.IsStale(result, agent.root, agent.lastPathTarget, destination, PATH_TARGET_MOVE_THRESHOLD) then
        Budget.Dispose(result)
        rebuildPath(agent, destination, speed)
        return true
    end
    agent.lastProgressPosition = agent.root.Position
    agent.lastProgressAt = os.clock()
    agent.nextPathAt = agent.lastProgressAt + PATH_REFRESH_SECONDS
    local path = result and result.path
    if path then
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
    return true
end

local function navigateTo(agent: any, destination: Vector3, speed: number)
    if not agent.active or not agent.root.Parent or not agent.humanoid.Parent then
        clearPath(agent)
        return
    end
    if consumePath(agent, destination, speed) then return end
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

-- Keep the same per-agent fields and defaults used by M94 navigation.
-- Initialization occurs before the agent is published to the AI registry.
function MonsterChaseNavigation.Initialize(agent: any)
    agent.navigating = false
    agent.navigationMode = ""
    agent.nextPathAt = 0
    agent.lastPathTarget = nil
    agent.path = nil
    agent.pathWaypoints = nil
    agent.pathIndex = 1
    agent.pathBlockedConnection = nil
    agent.pathRequest = nil
    agent.pathFallbackRequested = false
    agent.lastProgressPosition = agent.root.Position
    agent.lastProgressAt = os.clock()
end

MonsterChaseNavigation.ClearPath = clearPath
MonsterChaseNavigation.StopNavigation = stopNavigation
MonsterChaseNavigation.RunSpeedStuds = runSpeedStuds
MonsterChaseNavigation.NavigateTo = navigateTo

return table.freeze(MonsterChaseNavigation)
