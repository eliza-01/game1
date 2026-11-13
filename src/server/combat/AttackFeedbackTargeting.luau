-- Read-only authoritative reticle query for Miss/Far presentation.
-- This never contributes a hit, modifies HP, or affects the M317 bow snapshot.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("combat")
local Config = require(Shared:WaitForChild("AttackConfig"))
local Aim = require(Shared:WaitForChild("AttackAimGeometry"))
local BowRange = require(Shared:WaitForChild("BowRangeGeometry"))
local EntityHitboxService = require(script.Parent:WaitForChild("EntityHitboxService"))

local AttackFeedbackTargeting = {}

local function unobstructed(character: Model, target: Model, origin: Vector3, point: Vector3): boolean
    local displacement = point - origin
    if displacement.Magnitude <= 1e-6 then return true end
    local params = RaycastParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    params.RespectCanCollide = false
    params.FilterDescendantsInstances = {character}
    -- Ignore authoring/proxy hit surfaces which are not part of real target
    -- visibility. All other world geometry blocks misleading feedback.
    local excluded = {character}
    for _ = 1, 12 do
        local hit = Workspace:Raycast(origin, displacement, params)
        if not hit or hit.Distance >= displacement.Magnitude - 0.08
            or hit.Instance:IsDescendantOf(target) then
            return true
        end
        local part = hit.Instance
        if (part.Name == "RootCollider" and part:FindFirstAncestorOfClass("Model") ~= nil)
            or (part.Name == "LandscapeSwayTarget" and part:GetAttribute("Game1LandscapeSwayTarget") == true) then
            table.insert(excluded, part)
            params.FilterDescendantsInstances = excluded
        else
            return false
        end
    end
    return false
end

function AttackFeedbackTargeting.Evaluate(
    character: Model,
    root: BasePart,
    aimOrigin: any,
    aimDirection: any,
    attackRadius: number,
    isBow: boolean
): string?
    local origin, direction = Aim.Normalize(root.Position, aimOrigin, aimDirection)
    if not origin or not direction then return nil end
    local candidate = EntityHitboxService.RaycastAimRegions(character, origin, direction,
        Config.MaxAimDistance, isBow)
    if not candidate or not candidate.model or candidate.model:GetAttribute("LifeState") ~= "Alive"
        or not unobstructed(character, candidate.model, origin, candidate.hitPosition) then
        return nil
    end
    local within = if isBow
        then BowRange.Within(root.Position, candidate.hitPosition, attackRadius)
        else Aim.HitWithinAttackRadius(root.Position, candidate.hitPosition, attackRadius)
    if within then return "in_range" end
    if candidate.model:GetAttribute("Game1MonsterRuntime") == true then
        return "out_of_range_monster"
    end
    return nil
end

return table.freeze(AttackFeedbackTargeting)
