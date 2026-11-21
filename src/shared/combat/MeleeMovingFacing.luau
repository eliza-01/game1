-- Authoritative horizontal attack direction from a validated camera ray.
-- A melee hit has one server-clock HitEnd; locomotion direction never
-- overrides the reticle (the client separately owns leg/travel facing).
local MeleeMovingFacing = {}

local function horizontalUnit(value: any): Vector3?
    if typeof(value) ~= "Vector3" then return nil end
    if value.X ~= value.X or value.Z ~= value.Z
        or math.abs(value.X) == math.huge or math.abs(value.Z) == math.huge then return nil end
    local flat = Vector3.new(value.X, 0, value.Z)
    return if flat.Magnitude > 1e-5 then flat.Unit else nil
end

function MeleeMovingFacing.Resolve(rootFacing: Vector3, validatedAim: any): Vector3
    -- AttackService validates camera origin and direction before recording aim.
    -- Only a missing/invalid sample may fall back to the physical root.
    return horizontalUnit(validatedAim) or horizontalUnit(rootFacing) or Vector3.new(0, 0, -1)
end

return table.freeze(MeleeMovingFacing)
