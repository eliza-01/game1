--!strict
-- Pure 3D target-region test. The ray can hit the invisible socket's sphere
-- even when its exact Bone position is not under the crosshair.
local Aim = {}

function Aim.RaySphereEntry(origin: Vector3, direction: Vector3, center: Vector3, radius: number): number?
    if radius <= 0 or direction.Magnitude < 0.999 then return nil end
    local relative = center - origin
    local forward = relative:Dot(direction)
    if forward < -radius then return nil end
    local nearest = origin + direction * math.max(0, forward)
    local sideSq = (center - nearest).Magnitude ^ 2
    local radiusSq = radius * radius
    if sideSq > radiusSq then return nil end
    if relative.Magnitude < radius then
        -- A large aim zone can surround a third-person camera. Being inside
        -- must not activate the control when looking away from its center.
        local core = math.min(radius * 0.5, 2)
        if forward <= 0 or sideSq > core * core then return nil end
        return forward
    end
    return math.max(0, forward - math.sqrt(math.max(0, radiusSq - sideSq)))
end

return table.freeze(Aim)
