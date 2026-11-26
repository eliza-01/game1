-- Pure aim validation and headshot-ray geometry for server-authoritative melee.
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
    aimDirection: any
): (Vector3?, Vector3?)
    local origin, direction = AttackAimGeometry.Normalize(rootPosition, aimOrigin, aimDirection)
    if not origin or not direction then
        return nil, nil
    end

    -- Camera offset must not consume the classification budget. Rebase the
    -- exact reticle line; the resolver supplies the independent 32-stud limit.
    local closestAlongRay = math.max(0, (rootPosition - origin):Dot(direction))
    return origin + direction * closestAlongRay, direction
end

-- Range check for Miss/Far feedback only; not a headshot requirement.
function AttackAimGeometry.HitWithinAttackRadius(rootPosition: Vector3, hitPosition: any, attackRange: number): boolean
    return typeof(hitPosition) == "Vector3"
        and finiteVector(hitPosition)
        and finiteNumber(attackRange)
        and attackRange > 0
        and (hitPosition - rootPosition).Magnitude <= attackRange + Config.AttackRadiusEpsilon
end

return table.freeze(AttackAimGeometry)
