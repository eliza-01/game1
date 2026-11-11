-- Shared surface facing rule for landscape placement.
-- A published object's local front (-Z) points along the hit outward normal.
-- This is independent of camera direction and handles walls / ceilings.
local Surface = {}

function Surface.Facing(position: Vector3, normal: Vector3): CFrame
    if normal.Magnitude < 0.0001 then error("surface normal is missing") end
    local facing = normal.Unit
    local up = if math.abs(facing:Dot(Vector3.yAxis)) > 0.97
        then Vector3.zAxis else Vector3.yAxis
    return CFrame.lookAt(position, position + facing, up)
end

function Surface.Pivot(point: Vector3, normal: Vector3, settings): CFrame
    local offset = if settings.tetherEnabled then settings.length else 0
    local base = Surface.Facing(point + normal.Unit * offset, normal)
    return base * CFrame.Angles(
        math.rad(settings.pitch), math.rad(settings.yaw), math.rad(settings.roll))
end

function Surface.Raycast(workspace, mouse, maxDistance: number)
    local ray = mouse.UnitRay
    local ignore = {}
    local decor = workspace:FindFirstChild("Game1LandscapeDecor")
    if decor then table.insert(ignore, decor) end
    local camera = workspace.CurrentCamera
    if camera then table.insert(ignore, camera) end
    local params = RaycastParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    params.FilterDescendantsInstances = ignore
    params.IgnoreWater = true
    return workspace:Raycast(ray.Origin, ray.Direction * maxDistance, params)
end

return table.freeze(Surface)
