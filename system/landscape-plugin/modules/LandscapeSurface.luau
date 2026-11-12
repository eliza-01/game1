-- Canonical Location placement frame. Imported MeshPart/PivotOffset/Bone
-- coordinates remain owned by DecoAssetLoader; this module only calculates
-- where to move the intact model. Do not rebuild or move the rig's own pivot.
local DecoTransform = require(script.Parent.DecoTransform)

local Surface = {}

function Surface.Pivot(point: Vector3, normal: Vector3, settings,
    authoredRotation: CFrame, supportOffset: number, cameraLook: Vector3,
    targetKind: string): CFrame
    if normal.Magnitude < 0.0001 then error("surface normal is missing") end
    -- A surface contact is geometry-to-surface, not pivot-to-surface. This is
    -- the same authored-geometry offset used by DecoManager (including Z-up
    -- FBX axis correction); the original pivot stays inside the rig.
    -- For an authored stem the selected socket IS the pivot location.
    -- A tether always ends at the genuine authored pivot below its mount.
    local position = if settings.tetherEnabled then
        point - Vector3.yAxis * settings.length
        elseif targetKind == "surface" then
        point + normal.Unit * supportOffset
        else point
    local frame = DecoTransform.placementPivot(authoredRotation,
        position, normal, cameraLook)
    return frame * CFrame.Angles(math.rad(settings.pitch),
        math.rad(settings.yaw), math.rad(settings.roll))
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
