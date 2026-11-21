-- M358 · Environment bounce via narrow server rays, never through weapon-volume geometry.
local Workspace = game:GetService("Workspace")
local EnvironmentAssetService = require(script.Parent.Parent:WaitForChild("world"):WaitForChild("EnvironmentAssetService"))
local RealEstateEnvironmentTargets = require(script.Parent:WaitForChild("RealEstateEnvironmentTargets"))

local MeleeEnvironmentContact = {}

function MeleeEnvironmentContact.Query(root: BasePart, reach: number, angle: number,
        facingDirection: Vector3?): any?
    local params = RaycastParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    params.FilterDescendantsInstances = {root.Parent}
    params.RespectCanCollide = true
    params.IgnoreWater = true
    local chosen = facingDirection or root.CFrame.LookVector
    local facing = Vector3.new(chosen.X, 0, chosen.Z)
    if facing.Magnitude < 1e-5 then return nil end
    local origin = root.Position
    local halfAngle = math.rad(math.min(angle, 180) * 0.5)
    -- The bounce response is a directional impact, not an OBB sweep. Five rays
    -- preserve a broad-weapon feel without re-enabling weapon collision volumes.
    for _, fraction in ipairs({0, -0.5, 0.5, -1, 1}) do
        local direction = CFrame.fromAxisAngle(Vector3.yAxis, halfAngle * fraction):VectorToWorldSpace(facing.Unit)
        local hit = Workspace:Raycast(origin, direction * reach, params)
        if hit and hit.Instance:IsA("BasePart") then
            local model, definition = EnvironmentAssetService.ResolvePart(hit.Instance)
            if not model then model, definition = RealEstateEnvironmentTargets.ResolvePart(hit.Instance) end
            if model and definition and definition.destructible ~= true then
                return {model=model, definition=definition, part=hit.Instance, position=hit.Position, normal=hit.Normal}
            end
        end
    end
    return nil
end

return table.freeze(MeleeEnvironmentContact)
