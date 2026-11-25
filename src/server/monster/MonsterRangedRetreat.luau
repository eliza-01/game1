-- Ranged recovery movement. The attack executor owns cadence; the AI loop owns
-- calls to Step/Clear. No pathfinding, sideways fallback, damage or extra timers.
local Workspace = game:GetService("Workspace")
local Navigation = require(script.Parent:WaitForChild("MonsterChaseNavigation"))
local TargetPolicy = require(script.Parent:WaitForChild("MonsterTargetPolicy"))
local Presentation = require(script.Parent:WaitForChild("MonsterCombatPresentation"))
local HomeLeash = require(script.Parent.Parent:WaitForChild("actor"):WaitForChild("ActorHomeLeash"))
local Retreat = {}
local WINDOW = 0.4
local MAX_DISTANCE = 4
local STOP_DISTANCE = 0.5

function Retreat.IsRanged(model: Model): boolean
    return model:GetAttribute("MonsterCombatType") == "ranged"
end

function Retreat.FitPercent(timing: any, percent: number): number
    local playback = timing.playbackDuration
    local reserve = math.min(WINDOW, playback * 0.25)
    return math.clamp(percent * playback / math.max(0.001, playback - reserve), 1, 400)
end

-- Freeze the away direction at the beginning of recovery. If no legal space
-- exists, stay put; never pathfind around an obstacle or into another lane.
function Retreat.Candidates(position: Vector3, target: Vector3, reach: number, budget: number): {Vector3}
    local away = TargetPolicy.HorizontalDelta(target, position)
    if away.Magnitude < 0.001 then return {} end
    local distance = math.min(MAX_DISTANCE, budget, reach - away.Magnitude - STOP_DISTANCE)
    local points = {}
    while distance >= STOP_DISTANCE do
        table.insert(points, position + away.Unit * distance)
        distance -= STOP_DISTANCE
    end
    return points
end

local function destination(agent: any, targetRoot: BasePart, speed: number, remaining: number): Vector3?
    local position = agent.root.Position
    local params = RaycastParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    params.FilterDescendantsInstances = {agent.model}
    params.RespectCanCollide = true
    local ground = Workspace:Raycast(position, Vector3.new(0, -12, 0), params)
    if not ground then return nil end
    for _, point in ipairs(Retreat.Candidates(position, targetRoot.Position, TargetPolicy.AttackRadius(agent), speed * remaining)) do
        if HomeLeash.Outside(agent.spawnCenter, point, math.max(0, agent.homeRadius - STOP_DISTANCE)) then continue end
        -- The line can only move within its own small home pocket. The lane
        -- gate still controls the PLAYER's position, not the monster position.
        if TargetPolicy.IsStationary(agent.model) and TargetPolicy.HorizontalDistance(agent.home, point) > MAX_DISTANCE then continue end
        local delta = point - position
        if Workspace:Raycast(position, delta, params) then continue end
        local supported = true
        for step = 1, math.ceil(delta.Magnitude) do
            local sample = position + delta * (step / math.ceil(delta.Magnitude))
            local floor = Workspace:Raycast(sample + Vector3.yAxis, Vector3.new(0, -13, 0), params)
            if not floor or math.abs(floor.Position.Y - ground.Position.Y) > 1 then
                supported = false
                break
            end
        end
        if supported then return point end
    end
    return nil
end

function Retreat.Waiting(agent: any): boolean
    return agent.retreatPending == true
end

local function stopMove(agent: any)
    if agent.retreatDestination then
        agent.retreatDestination = nil
        Navigation.StopNavigation(agent)
    end
end

function Retreat.Clear(agent: any)
    stopMove(agent)
    agent.retreatPending = false
    agent.retreatStarted = false
end

function Retreat.Step(agent: any, targetRoot: BasePart, now: number): boolean
    if not Retreat.Waiting(agent) then return false end
    local remaining = agent.nextAttackAt - now
    if remaining <= 0 then Retreat.Clear(agent); return false end
    if not agent.retreatStarted then
        agent.retreatStarted = true
        local speed = Navigation.RunSpeedStuds(agent)
        local point = destination(agent, targetRoot, speed, remaining)
        if point then
            Navigation.StopNavigation(agent)
            agent.retreatDestination = point
            agent.humanoid.AutoRotate = true
            agent.humanoid.WalkSpeed = speed
            agent.humanoid:MoveTo(point)
            Presentation.PlayRun(agent)
        end
    end
    local point = agent.retreatDestination
    if point and (TargetPolicy.HorizontalDistance(agent.root.Position, point) <= STOP_DISTANCE
        or TargetPolicy.HorizontalDistance(agent.root.Position, targetRoot.Position) >= TargetPolicy.AttackRadius(agent)) then
        stopMove(agent)
    end
    if not agent.retreatDestination then Presentation.PlayCombatIdle(agent) end
    return true
end

return table.freeze(Retreat)
