--!strict
-- Server -> owning client, v1: (character Model, world forward Vector3).
-- No client requests; physical placement remains server-owned.
local Heading = {}
Heading.RemoteName = "CharacterCameraAlignV1"

function Heading.Yaw(forward: Vector3): number?
    local x, z = forward.X, forward.Z
    if x ~= x or z ~= z or math.abs(x) == math.huge or math.abs(z) == math.huge then return nil end
    if x * x + z * z < 1e-8 then return nil end
    return math.atan2(-x, -z)
end

return table.freeze(Heading)
