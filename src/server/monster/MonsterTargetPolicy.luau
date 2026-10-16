-- Monster target acquisition and hit validation policy. No movement, state writes or attack timers.
-- The combat AI owns when to scan and when to act on a selected target.
local Players = game:GetService("Players")
local Workspace = game:GetService("Workspace")

local MonsterTargetPolicy = {}
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

local function attackStillConnects(agent: any, target: Model): boolean
    local targetRoot = rootOf(target)
    if not targetIsValid(target) or not targetRoot then return false end
    local delta = horizontalDelta(agent.root.Position, targetRoot.Position)
    if delta.Magnitude > attackRadius(agent) or math.abs(targetRoot.Position.Y - agent.root.Position.Y) > VERTICAL_TOLERANCE then return false end
    if delta.Magnitude > 0.001 then
        if agent.root.CFrame.LookVector:Dot(delta.Unit) < math.cos(math.rad(ATTACK_ARC_DEGREES * 0.5)) then return false end
    end
    return hasLineOfSight(agent, target)
end

MonsterTargetPolicy.RootOf = rootOf
MonsterTargetPolicy.NavigationRootOf = navigationRootOf
MonsterTargetPolicy.IsValid = targetIsValid
MonsterTargetPolicy.HorizontalDelta = horizontalDelta
MonsterTargetPolicy.HorizontalDistance = horizontalDistance
MonsterTargetPolicy.IsAggressive = aggressive
MonsterTargetPolicy.AggroRadius = aggroRadius
MonsterTargetPolicy.AttackRadius = attackRadius
MonsterTargetPolicy.AcquireNearestTarget = acquireNearestTarget
MonsterTargetPolicy.AttackStillConnects = attackStillConnects

return table.freeze(MonsterTargetPolicy)
