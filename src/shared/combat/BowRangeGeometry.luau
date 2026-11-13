-- Pure character-centered bow range. The Studio ring visualizes the horizontal
-- ground radius, not the distance from a shoulder camera or arrow nock.
local Range = {}
local function finite(n: number): boolean
    return n == n and n > -math.huge and n < math.huge
end

function Range.Within(root: Vector3, contact: Vector3, radius: number): boolean
    if typeof(root) ~= "Vector3" or typeof(contact) ~= "Vector3"
        or not finite(radius) or radius <= 0 then return false end
    local delta = contact - root
    return delta.X * delta.X + delta.Z * delta.Z <= (radius + 0.15) ^ 2
        and math.abs(delta.Y) <= radius + 0.15
end

function Range.CastDistance(root: Vector3, camera: Vector3, radius: number, maximum: number): number
    -- Valid camera origins are limited elsewhere by AttackAimGeometry.Normalize.
    return math.min(maximum, radius + (camera - root).Magnitude + 2)
end
return table.freeze(Range)
