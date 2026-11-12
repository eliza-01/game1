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

-- Find the low-arc direction that intersects the chosen reticle point. When the
-- physical solution is impossible, use a straight aim rather than invent speed.
function BowAimGeometry.BallisticDirection(origin: Vector3, target: Vector3, speed: number, gravity: number): Vector3?
    local displacement = target - origin
    if displacement.Magnitude < 0.01 then return nil end
    local flat = Vector3.new(displacement.X, 0, displacement.Z)
    local distance = flat.Magnitude
    if distance < 0.01 or gravity <= 0 then return displacement.Unit end
    local speedSq = speed * speed
    local disc = speedSq * speedSq - gravity * (gravity * distance * distance + 2 * displacement.Y * speedSq)
    if disc < 0 then return displacement.Unit end
    local tangent = (speedSq - math.sqrt(disc)) / (gravity * distance)
    return (flat.Unit + Vector3.yAxis * tangent).Unit
end

return table.freeze(BowAimGeometry)
