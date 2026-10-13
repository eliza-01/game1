-- Shared server combat queries for player-targeted world actors (monsters, NPCs).
-- No player damage is trusted from client-provided target positions.
local Players = game:GetService("Players")
local Workspace = game:GetService("Workspace")

local ActorCombatTargeting = {}

function ActorCombatTargeting.Root(model: Model?): BasePart?
    if not model then return nil end
    local candidate = model:FindFirstChild("RootCollider") or model:FindFirstChild("HumanoidRootPart") or model.PrimaryPart
    return if candidate and candidate:IsA("BasePart") then candidate else nil
end

function ActorCombatTargeting.Valid(target: Model?): boolean
    return target ~= nil and target.Parent ~= nil
        and target:GetAttribute("Damageable") == true
        and target:GetAttribute("LifeState") == "Alive"
        and ActorCombatTargeting.Root(target) ~= nil
end

function ActorCombatTargeting.Distance(a: Vector3, b: Vector3): number
    return Vector3.new(a.X - b.X, 0, a.Z - b.Z).Magnitude
end

function ActorCombatTargeting.ClosestPlayer(position: Vector3, radius: number): Model?
    local target: Model? = nil
    local best = radius
    for _, player in ipairs(Players:GetPlayers()) do
        local character = player.Character
        local root = ActorCombatTargeting.Root(character)
        if root and ActorCombatTargeting.Valid(character) then
            local distance = ActorCombatTargeting.Distance(position, root.Position)
            if distance <= best then
                best, target = distance, character
            end
        end
    end
    return target
end

function ActorCombatTargeting.Visible(attacker: Model, origin: Vector3, target: Model): boolean
    local targetRoot = ActorCombatTargeting.Root(target)
    if not targetRoot then return false end
    local params = RaycastParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    params.FilterDescendantsInstances = { attacker }
    params.RespectCanCollide = false
    local ray = targetRoot.Position + Vector3.new(0, 0.6, 0) - origin
    local hit = Workspace:Raycast(origin, ray, params)
    return not hit or hit.Instance:IsDescendantOf(target)
end

return table.freeze(ActorCombatTargeting)
