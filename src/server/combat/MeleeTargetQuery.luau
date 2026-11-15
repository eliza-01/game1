-- M358 · Server-only melee query: authored hitbox geometry + world occlusion.
local Workspace = game:GetService("Workspace")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Geometry = require(ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("combat"):WaitForChild("MeleeArcGeometry"))
local EntityHitboxService = require(script.Parent:WaitForChild("EntityHitboxService"))

local MeleeTargetQuery = {}

function MeleeTargetQuery.Height(root: BasePart, padding: number): (number, number)
    -- RootCollider is the authoritative collision envelope, including custom scaling.
    local halfHeight = math.max(1.5, root.Size.Y * 0.5)
    return root.Position.Y - halfHeight - padding, root.Position.Y + halfHeight + padding
end

function MeleeTargetQuery.IsUnobstructed(character: Model, model: Model, root: BasePart, point: Vector3,
    params: RaycastParams?): boolean
    local chest = root.Position + Vector3.new(0, math.min(1, root.Size.Y * 0.25), 0)
    local displacement = point - chest
    if displacement.Magnitude <= 1e-4 then return true end
    if not params then
        params = RaycastParams.new()
        params.FilterType = Enum.RaycastFilterType.Exclude
        params.FilterDescendantsInstances = { character }
        params.RespectCanCollide = true
        params.IgnoreWater = false
    end
    local hit = Workspace:Raycast(chest, displacement, params)
    return hit == nil or hit.Instance:IsDescendantOf(model)
end

function MeleeTargetQuery.Find(character: Model, root: BasePart, reach: number, angle: number, padding: number): {any}
    local minY, maxY = MeleeTargetQuery.Height(root, padding)
    local candidates = EntityHitboxService.QueryDamageablesInArc(character, root.Position, root.CFrame.LookVector,
        reach, angle, minY, maxY, Geometry)
    local results = {}
    if #candidates == 0 then return results end
    -- One filter allocation per attack snapshot, not per eligible victim.
    local params = RaycastParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    params.FilterDescendantsInstances = { character }
    params.RespectCanCollide = true
    params.IgnoreWater = false
    for _, candidate in ipairs(candidates) do
        if MeleeTargetQuery.IsUnobstructed(character, candidate.model, root, candidate.hit.hitPosition, params) then
            table.insert(results, candidate)
        end
    end
    return results
end

return table.freeze(MeleeTargetQuery)
