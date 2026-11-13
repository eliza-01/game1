-- Pure shared bow aiming mathematics. Client request never authorizes damage.
local AttackAimGeometry = require(script.Parent:WaitForChild("AttackAimGeometry"))
local Policy = require(script.Parent:WaitForChild("BowProjectileConfig"))
local BowAimGeometry = {}

function BowAimGeometry.Validate(root: BasePart, origin: any, direction: any): (Vector3?, Vector3?)
    local cameraOrigin, unitDirection = AttackAimGeometry.Normalize(root.Position, origin, direction)
    if not cameraOrigin or not unitDirection then return nil, nil end
    local localDirection = root.CFrame:VectorToObjectSpace(unitDirection)
    local horizontal = math.sqrt(localDirection.X ^ 2 + localDirection.Z ^ 2)
    local yaw = math.atan2(localDirection.X, -localDirection.Z)
    local pitch = math.atan2(localDirection.Y, math.max(horizontal, 1e-6))
    if math.abs(yaw) > Policy.MaxAimYaw
        or pitch < Policy.MinAimPitch or pitch > Policy.MaxAimPitch then
        return nil, nil
    end
    return cameraOrigin, unitDirection
end

function BowAimGeometry.ValidateLaunch(root: BasePart, candidate: any): Vector3?
    if typeof(candidate) ~= "Vector3" then return nil end
    local delta = candidate - root.Position
    if delta.X ~= delta.X or delta.Y ~= delta.Y or delta.Z ~= delta.Z
        or math.abs(delta.X) == math.huge or math.abs(delta.Y) == math.huge
        or math.abs(delta.Z) == math.huge or delta.Magnitude > Policy.MaxLaunchOffset then
        return nil
    end
    return candidate
end

return table.freeze(BowAimGeometry)
