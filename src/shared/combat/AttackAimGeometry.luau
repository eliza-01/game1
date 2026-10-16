-- Pure aim validation and finite center-screen ray geometry for server-authoritative melee.
-- No player, workspace, attack lifecycle, or mutable session state.
local Config = require(script.Parent:WaitForChild("AttackConfig"))
local AttackAimGeometry = {}

local function finiteNumber(value: number): boolean
    return value == value and value > -math.huge and value < math.huge
end

local function finiteVector(value: Vector3): boolean
    return finiteNumber(value.X) and finiteNumber(value.Y) and finiteNumber(value.Z)
end

function AttackAimGeometry.Normalize(rootPosition: Vector3, aimOrigin: any, aimDirection: any): (Vector3?, Vector3?)
    if typeof(aimOrigin) ~= "Vector3"
        or typeof(aimDirection) ~= "Vector3"
        or not finiteVector(aimOrigin)
        or not finiteVector(aimDirection)
        or (aimOrigin - rootPosition).Magnitude > Config.HeadshotAimOriginMaxDistance
    then
        return nil, nil
    end

    local magnitude = aimDirection.Magnitude
    if magnitude <= 1e-6 then
        return nil, nil
    end
    return aimOrigin, aimDirection / magnitude
end

function AttackAimGeometry.HeadshotSegment(
    rootPosition: Vector3,
    aimOrigin: any,
    aimDirection: any,
    attackRange: number
): (Vector3?, Vector3?)
    local origin, direction = AttackAimGeometry.Normalize(rootPosition, aimOrigin, aimDirection)
    if not origin or not direction then
        return nil, nil
    end

    -- Camera distance must not consume melee range. Keep the exact center-screen
    -- line, but rebase its finite segment to the point on that line closest to
    -- the attacker. The segment then extends exactly AttackRadius forward.
    local closestAlongRay = math.max(0, (rootPosition - origin):Dot(direction))
    return origin + direction * closestAlongRay, direction
end

function AttackAimGeometry.InterpolateDirection(previous: Vector3?, current: Vector3?, alpha: number): Vector3?
    if typeof(current) ~= "Vector3" then
        return nil
    end
    if typeof(previous) ~= "Vector3" then
        return current
    end
    local blended = previous:Lerp(current, alpha)
    if blended.Magnitude <= 1e-6 then
        return current
    end
    return blended.Unit
end

return table.freeze(AttackAimGeometry)
