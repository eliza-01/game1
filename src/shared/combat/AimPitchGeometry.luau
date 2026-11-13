-- Pure presentation pitch, independent of hitbox height and the server hit ray.
-- A nearby impact can be *above* RootCollider while the actual reticle ray
-- points downward. Never derive head elevation from that impact displacement.
local AimPitchGeometry = {}

function AimPitchGeometry.Resolve(
    rayDirection: Vector3?, targetDisplacement: Vector3,
    neutralDistance: number, fullDistance: number
): number
    if typeof(rayDirection) ~= "Vector3" or rayDirection.Magnitude <= 1e-6 then
        return 0 -- no valid camera direction: stay level, never snap upward
    end
    local horizontal = math.sqrt(rayDirection.X ^ 2 + rayDirection.Z ^ 2)
    local cameraPitch = math.atan2(rayDirection.Y, math.max(horizontal, 1e-6))
    if cameraPitch >= 0 then
        return cameraPitch -- deliberate upward aim must work even point-blank
    end

    local targetDistance = math.sqrt(targetDisplacement.X ^ 2 + targetDisplacement.Z ^ 2)
    local width = math.max(0.001, fullDistance - neutralDistance)
    local t = math.clamp((targetDistance - neutralDistance) / width, 0, 1)
    local smooth = t * t * (3 - 2 * t)
    return cameraPitch * smooth
end

return table.freeze(AimPitchGeometry)
