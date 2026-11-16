-- Pure equip-time policy: how far the camera may sit from the physical root
-- while the server's horizontal melee sector still covers the reticle.
-- This module never queries targets or changes authoritative hit geometry.
local AttackConfig = require(script.Parent:WaitForChild("AttackConfig"))

local MeleeFacingPolicy = {}

-- Keep the reticle comfortably INSIDE the damaging sector instead of on its edge.
-- This fraction scales with the equipped arc, not a hard-coded turn angle.
local INNER_ARC_FRACTION = 0.85

function MeleeFacingPolicy.MaxResidualYaw(arcDegrees: any): number
    local angle = math.clamp(tonumber(arcDegrees) or AttackConfig.MeleeDefaultArcAngle, 1, 360)
    if angle >= 360 then
        -- A full-circle attack cannot miss because of yaw; no root correction.
        return math.pi
    end
    -- The spine cannot twist beyond its own physical presentation limit.
    -- Narrower sectors require more root turn, broader sectors require less.
    return math.min(AttackConfig.TorsoYawLimit, math.rad(angle * 0.5) * INNER_ARC_FRACTION)
end

return table.freeze(MeleeFacingPolicy)
